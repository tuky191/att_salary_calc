import datetime
from datetime import timedelta
import re
from pprint import pprint
from tulip_api import TulipApi


class PayCalculator():

    def __init__(self, username='', password=''):
        self.tulip_api = TulipApi(username=username, password=password)
        self.calculation_input = {}
        self.attendance = {}
        self.worked_days = {}
        self.public_holidays = {}

    def calculate(self,
                  username,
                  contractual_base_pay,
                  ppu,
                  month='',
                  year='',
                  other_pay=0):
        self.contractual_base_pay = contractual_base_pay
        self.ppu = ppu
        self.tulip_api.set_user(username)

        self.calculation_output = {
            'total': 0,
            'pay_during_working_time': 0,
            'weekend': {
                '10pc': 0,
                '50pc': 0
            },
            'base_wage': 0,
            'night': 0,
            'ph': 0,
            'vacation': 0,
            'other_pay': other_pay
        }
        self.get_days_base(month=month, year=year)
        self.get_attendance()
        self.quantify_shift_codes()
        self.prepare_computation_inputs()
        self.calculate_salary()
        pprint(self.calculation_input)
        return self.calculation_output

    def get_counts_between_hours(self,
                                 start_time='',
                                 end_time='',
                                 break_start='',
                                 break_end=''):
        quarter_hourly = []
        hours_count = {}
        hours_count = {
            'base': {
                'hours': 0,
                'minutes': 0
            },
            'weekend': {
                'hours': 0,
                'minutes': 0
            },
            'night': {
                'hours': 0,
                'minutes': 0
            }
        }
        night_hours = [22, 23, 0, 1, 2, 3, 4, 5]
        current_time_obj = datetime.datetime.strptime(
            start_time, '%Y-%m-%dT%H:%M:%S') - timedelta(minutes=15)

        end_time_obj = datetime.datetime.strptime(end_time,
                                                  '%Y-%m-%dT%H:%M:%S')
        break_start_obj = datetime.datetime.strptime(break_start,
                                                     '%Y-%m-%dT%H:%M:%S')
        break_end_obj = datetime.datetime.strptime(break_end,
                                                   '%Y-%m-%dT%H:%M:%S')
        break_difference = break_end_obj - break_start_obj

        while end_time_obj - timedelta(minutes=15) > current_time_obj:
            current_time_obj += timedelta(minutes=15)
            quarter_hourly.append(current_time_obj)

        for quarter_hour in quarter_hourly:
            hours_count['base']['minutes'] += 15
            if quarter_hour.weekday() >= 5:
                hours_count['weekend']['minutes'] += 15
            if quarter_hour.hour in night_hours:
                hours_count['night']['minutes'] += 15

        base = hours_count['base']['minutes']
        for key, _value in hours_count.items():
            if hours_count[key]['minutes'] != 0 and base == hours_count[key][
                    'minutes']:
                hours_count[key]['minutes'] -= int(break_difference.seconds /
                                                   60)
                hours_count[key]['hours'] = hours_count[key]['minutes'] / 60
                continue
            elif hours_count[key]['minutes'] != 0:
                hours_count[key]['hours'] = hours_count[key]['minutes'] / 60

        return hours_count

    def calculate_salary(self):

        self.calculation_output['base_wage'] = self.calculate_basic_wage()
        try:
            self.calculation_output['weekend']['50pc'] = self.calculate_uplift(
                coeficient=0.5,
                hours=self.calculation_input['worked']['minutes']['weekend'] /
                60)
        except KeyError:
            self.calculation_output['weekend']['50pc'] = 0

        try:
            self.calculation_output['night'] = self.calculate_uplift(
                coeficient=0.5,
                hours=self.calculation_input['worked']['minutes']['night'] /
                60)
        except KeyError:
            self.calculation_output['night'] = 0

        try:
            self.calculation_output['ph'] = self.calculate_uplift(
                coeficient=1,
                hours=self.calculation_input['public_holiday']['minutes']
                ['base'] / 60)
        except KeyError:
            self.calculation_output['ph'] = 0

        try:
            self.calculation_output['weekend']['10pc'] = self.calculate_uplift(
                coeficient=0.1,
                hours=self.calculation_input['public_holiday']['minutes']
                ['weekend'] / 60)
        except KeyError:
            self.calculation_output['weekend']['10pc'] = 0

        try:
            self.calculation_output['vacation'] = self.calculate_uplift(
                coeficient=1,
                hours=self.calculation_input['vacation']['minutes']['base'] /
                60)
        except KeyError:
            self.calculation_output['vacation'] = 0

        self.calculation_output['pay_during_working_time'] = self.calculation_output['base_wage'] + \
            self.calculation_output['weekend']['50pc'] + \
            self.calculation_output['weekend']['10pc'] + \
            self.calculation_output['night'] + \
            self.calculation_output['ph']

        self.calculation_output['total'] = self.calculation_output['pay_during_working_time'] + \
            self.calculation_output['vacation'] + \
            self.calculation_output['other_pay']

    def calculate_uplift(self, coeficient=1, hours=0):
        return int(round((self.ppu * coeficient) * hours, 0))

    def calculate_basic_wage(self):

        try:
            vacation = self.calculation_input['vacation']['minutes']['base']
        except KeyError:
            vacation = 0
        basic_wage = int(
            round((self.contractual_base_pay / (
                (vacation +
                 self.calculation_input['worked']['minutes']['base']) / 60)) *
                  (self.calculation_input['worked']['minutes']['base'] / 60),
                  0))
        return basic_wage

    def quantify_shift_codes(self):
        self.quantified_per_shift_code = {}
        for day, value in self.attendance.items():
            if value['code'] not in self.quantified_per_shift_code.keys():
                self.quantified_per_shift_code[value['code']] = []
                self.quantified_per_shift_code[value['code']].append(
                    {day: value})
            else:
                self.quantified_per_shift_code[value['code']].append(
                    {day: value})
            self.quantified_per_shift_code.update(
                {value['code']: self.quantified_per_shift_code[value['code']]})
        return self.quantified_per_shift_code

    def get_attendance(self):
        self.attendance = {}
        # free_days = self.tulip_api.get_free_days(start_time, end_time)

        for key, day in self.worked_days.items():
            shift = {}
            shift['code'] = ''
            datime_obj = datetime.datetime.strptime(key, '%Y-%m-%dT%H:%M:%S')
            shift['day_of_week'] = datime_obj.strftime('%A')
            if day['codeForShiftOverwrite']:
                shift['code'] = day['codeForShiftOverwrite']
            if day['requests']:
                request = day['requests'].pop()
                shift['code'] = request['shiftPlanAttendanceActivityId'][
                    'code']
                shift['description'] = request[
                    'shiftPlanAttendanceActivityId']['description']
            if not shift['code']:
                # SSDD, same shit, different day
                shift['code'] = 'SSDD'
                shift['description'] = 'Same shift different day'
            shift['shift_code'] = day['shiftPlanWorkshiftId']['code']
            shift['lenght'] = day['shiftPlanWorkshiftId']['shiftLength']
            shift['shift_start'] = day['shiftPlanWorkshiftId']['workStart']
            shift['shift_end'] = day['shiftPlanWorkshiftId']['workEnd']
            shift['work_start'] = day['timesheetDetails'][0]['workStart']
            shift['work_end'] = day['timesheetDetails'][0]['workEnd']
            shift['break_start'] = day['timesheetDetails'][0]['break1Start']
            shift['break_end'] = day['timesheetDetails'][0]['break1End']
            shift['hours_count'] = self.get_counts_between_hours(
                start_time=shift['work_start'],
                end_time=shift['work_end'],
                break_start=shift['break_start'],
                break_end=shift['break_end'])
            self.attendance.update({key: shift})
        return self.attendance

    def prepare_computation_inputs(self):
        self.quantified_per_shift_code
        self.calculation_input = {
            'days_counted_for_bonus': 0,
            'working_fund_days': 0,
            'public_holiday_not_worked': 0,
            'sickness_absence': 0,
            'overtime': {
                'days': 0,
                'minutes': {}
            },
            'public_holiday': {
                'days': 0,
                'minutes': {}
            },
            'worked': {
                'days': 0,
                'minutes': {
                    'base': 0,
                    'lenght': 0,
                    'night': 0,
                    'weekend': 0
                }
            },
            'vacation': {
                'days': 0,
                'minutes': {}
            },
        }

        annual_bonus_calculation_codes = ['VO', 'SSDD', 'PH', 'PHS']
        been_at_work_calculation_codes = ['VO', 'SSDD', 'PHS', 'OT']
        for code, days_list in self.quantified_per_shift_code.items():
            self.calculation_input['working_fund_days'] += len(days_list)
            if code == 'PH':
                self.calculation_input['public_holiday_not_worked'] += len(
                    days_list)
            if code == 'I':
                self.calculation_input['sickness_absence'] += len(days_list)

            if code in been_at_work_calculation_codes:
                self.calculation_input['worked']['days'] += len(days_list)
                result = self.count_minutes_base(days_list)
                self.calculation_input['worked']['minutes']['base'] += result[
                    'base']
                self.calculation_input['worked']['minutes'][
                    'lenght'] += result['lenght']
                self.calculation_input['worked']['minutes']['night'] += result[
                    'night']
                self.calculation_input['worked']['minutes'][
                    'weekend'] += result['weekend']
                pprint(self.calculation_input['worked']['minutes'])

            if code in annual_bonus_calculation_codes:
                self.calculation_input['days_counted_for_bonus'] += len(
                    days_list)

            if code == 'PHS':
                self.calculation_input['public_holiday']['days'] += len(
                    days_list)
                self.calculation_input['public_holiday'][
                    'minutes'] = self.count_minutes(days_list)

            if code == 'OT':
                self.calculation_input['overtime']['days'] += len(days_list)
                self.calculation_input['overtime'][
                    'minutes'] = self.count_minutes(days_list)

            if code == 'V':
                self.calculation_input['vacation']['days'] += len(days_list)
                self.calculation_input['vacation'][
                    'minutes'] = self.count_minutes(days_list)

    def count_minutes(self, days_list):
        count = {'lenght': 0, 'base': 0, 'night': 0, 'weekend': 0}
        for day in days_list:
            key = (list(day.keys()).pop())
            if ((day[key]['code'] == 'OT' or day[key]['code'] == 'PHS') and
                    re.search('paid', day[key]['description'],
                              re.MULTILINE)) or (day[key]['code'] != 'PHS'
                                                 and day[key]['code'] != 'OT'):
                count['lenght'] += day[key]['lenght']
                count['base'] += day[key]['hours_count']['base']['minutes']
                count['night'] += day[key]['hours_count']['night']['minutes']
                count['weekend'] += day[key]['hours_count']['weekend'][
                    'minutes']

            if ((day[key]['code'] == 'PHS') and not re.search(
                    'paid', day[key]['description'], re.MULTILINE)):
                count['weekend'] += day[key]['hours_count']['weekend'][
                    'minutes']

        return count

    def count_minutes_base(self, days_list):
        count = {'lenght': 0, 'base': 0, 'night': 0, 'weekend': 0}
        for day in days_list:
            key = (list(day.keys()).pop())
            if ((day[key]['code'] != 'PHS')):
                count['lenght'] += day[key]['lenght']
                count['base'] += day[key]['hours_count']['base']['minutes']
                count['night'] += day[key]['hours_count']['night']['minutes']
                count['weekend'] += day[key]['hours_count']['weekend'][
                    'minutes']

            elif ((day[key]['code'] == 'PHS')):
                count['lenght'] += day[key]['lenght']
                count['base'] += day[key]['hours_count']['base']['minutes']
                count['night'] += day[key]['hours_count']['night']['minutes']
                count['weekend'] += 0
        # pprint(count)
        return count

    def get_days_base(self, month='', year=''):
        attendance_data = self.tulip_api.get_month_attendance(month=month,
                                                              year=year)
        self.worked_days = {}
        for _key, value in enumerate(attendance_data['shiftPlanDayData']):
            if value[0]['shiftPlanWorkshiftId']:
                self.worked_days.update({value[0]['date']: value[0]})
        return self.worked_days
