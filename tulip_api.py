from browser import Browser
from bs4 import BeautifulSoup
import xlrd
from pprint import pprint
import urllib
from urllib.parse import urlparse
import json
import logging
import calendar
import datetime
import re

logging.basicConfig(format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.DEBUG)


class TulipApi():

    def __init__(self, username='', password=''):

        self.browser = Browser(username=username, password=password)
        self.shifts_list = []
        self.attendance_activities = []
        self.current_form = ''
        self.current_page = ''
        self.employee_dll_class = ''
        self.username = ''
        self.tulip_api_json_base_url = 'https://att.tulipize.com/api/ShiftPlan/'
        self.get_basic_details()

    def set_user(self, username):
        self.username = username
        self.get_basic_details()

    def get_basic_details(self):
        self.browser.request(
            'https://att.tulipize.com/Attendance/AttendanceOverview.aspx')
        soup = BeautifulSoup(self.browser.current_page, "html.parser")
        self.get_forms(soup)
        self.get_employee_number(soup)
        self.get_team_id(soup)

    def get_month_attendance(self, month='', year=''):
        num_days = calendar.monthrange(year, month)[1]
        days = [
            datetime.date(year, month, day) for day in range(1, num_days + 1)
        ]
        first_day = days.pop(0)
        last_day = days.pop()
        return self.get_full_shift_plan_data(
            first_day.strftime('%Y-%m-%dT%H:%M:%S'),
            last_day.strftime('%Y-%m-%dT%H:%M:%S'))

    def get_month_public_holidays(self, month='', year=''):
        num_days = calendar.monthrange(year, month)[1]
        days = [
            datetime.date(year, month, day) for day in range(1, num_days + 1)
        ]
        first_day = days.pop(0)
        last_day = days.pop()
        return self.get_free_days(first_day.strftime('%Y-%m-%dT%H:%M:%S'),
                                  last_day.strftime('%Y-%m-%dT%H:%M:%S'))

    def get_full_shift_plan_data(self, start_date, end_date, all_data=False):
        # start_date / end_date must be in datetime format 2020-03-01T00:00:00 01:00
        request = {
            'method': 'GetFullShiftPlanData',
            'teamId': self.team_id,
            'startDate': start_date,
            'endDate': end_date
        }
        query = self.build_url(**request)
        self.browser.request(query)
        shift_plan_data = json.loads(self.browser.current_page)
        keys_to_unset = [
            'employeeIdsWithError', 'errorCount', 'presenceAtWorkSummary',
            'shiftPlanIsValid', 'shiftPlanTeams', 'validationMessage',
            'warningCount', 'workTimeSummary'
        ]
        shift_plan_data = {
            key: shift_plan_data[key]
            for key in shift_plan_data if key not in keys_to_unset
        }
        if all_data == True:
            return shift_plan_data
        else:
            shift_plan_data['shiftPlanDayData'] = [[
                employee for employee in day if employee.get(
                    'shiftPlanEmployeeId') == int(self.employee_number)
            ] for day in shift_plan_data['shiftPlanDayData']]
            shift_plan_data['shiftPlanEmployees'] = [
                employee for employee in shift_plan_data['shiftPlanEmployees']
                if employee.get('id') == int(self.employee_number)
            ]
            self.add_shift_plan_workshift_from_id(shift_plan_data)
            return shift_plan_data

    def add_shift_plan_workshift_from_id(self, dictionary):
        for key_day, _day in enumerate(dictionary['shiftPlanDayData']):
            for key_employee, _employee in enumerate(
                    dictionary['shiftPlanDayData'][key_day]):
                if dictionary['shiftPlanDayData'][key_day][key_employee][
                        'shiftPlanWorkshiftId']:
                    dictionary['shiftPlanDayData'][key_day][key_employee][
                        'shiftPlanWorkshiftId'] = self.get_shift_plan_workshifts(
                            id=dictionary['shiftPlanDayData'][key_day]
                            [key_employee]['shiftPlanWorkshiftId']).pop()
                if dictionary['shiftPlanDayData'][key_day][key_employee][
                        'requests']:
                    for key_request, request in enumerate(
                            dictionary['shiftPlanDayData'][key_day]
                        [key_employee]['requests']):
                        dictionary['shiftPlanDayData'][key_day][key_employee][
                            'requests'][key_request][
                                'shiftPlanAttendanceActivityId'] = self.get_shift_plan_attendance_activities(
                                    id=request['shiftPlanAttendanceActivityId']
                                ).pop()

    def get_shift_plan_calendars(self, start_date, end_date):
        # start_date / end_date must be in datetime format 2020-03-01T00:00:00
        request = {
            'method': 'GetShiftPlanCalendars',
            'teamId': self.team_id,
            'startDate': start_date,
            'endDate': end_date
        }
        query = self.build_url(**request)
        self.browser.request(query)
        return json.loads(self.browser.current_page)

    def get_free_days(self, start_date, end_date):
        # start_date / end_date must be in datetime format 2020-03-01T00:00:00 01:00
        request = {
            'method': 'GetFreeDays',
            'teamId': self.team_id,
            'startDate': start_date,
            'endDate': end_date
        }
        query = self.build_url(**request)
        self.browser.request(query)
        return json.loads(self.browser.current_page)

    def get_shift_plan_workshifts(self, id=False):
        if not self.shifts_list:
            request = {
                'method': 'GetShiftPlanWorkshifts',
                'teamId': self.team_id
            }
            query = self.build_url(**request)
            self.browser.request(query)
            self.shifts_list = json.loads(self.browser.current_page)
        if not id:
            return self.shifts_list
        else:
            return [
                shift for shift in self.shifts_list if shift.get('id') == id
            ]

    def get_shift_plan_attendance_activities(self, id=False):
        if not self.attendance_activities:
            request = {
                'method': 'GetShiftPlanAttendanceActivities',
                'teamId': self.team_id
            }
            query = self.build_url(**request)
            self.browser.request(query)
            self.attendance_activities = json.loads(self.browser.current_page)
        if not id:
            return self.attendance_activities
        else:
            return [
                activity for activity in self.attendance_activities
                if activity.get('id') == id
            ]

    def get_shift_plan_available_years(self):
        request = {'method': 'GetShiftPlanAvailableYears'}
        query = self.build_url(**request)
        self.browser.request(query)
        return json.loads(self.browser.current_page)

    def build_url(self, **kwargs):
        method = kwargs.pop('method', None)
        if method:
            return self.tulip_api_json_base_url + method + '?' + urllib.parse.urlencode(
                kwargs)
        else:
            return self.tulip_api_json_base_url + '?' + urllib.parse.urlencode(
                kwargs)

    def get_timesheet_details(self, **kwargs):
        if not kwargs:
            self.browser.request(
                'https://att.tulipize.com/Attendance/AttendanceTimesheet-Edit.aspx'
            )
        else:
            self.browser.request(
                'https://att.tulipize.com/Attendance/AttendanceTimesheet-Edit.aspx',
                kwargs)

        soup = BeautifulSoup(self.browser.current_page, "html.parser")
        self.get_forms(soup)
        self.get_employee_number(soup)

    def one_month_back(self):
        post_data = {
            '__EVENTTARGET':
            'ctl00$ctl00$MainCPH$MainCPH$DayViewRepeater$ctl00$ctl02',
            'ctl00$ctl00$MainCPH$MainCPH$EmployeeDDL': self.employee_number
        }
        self.get_timesheet_details(**{**self.current_form, **post_data})

    def one_month_forward(self):
        post_data = {
            '__EVENTTARGET':
            'ctl00$ctl00$MainCPH$MainCPH$DayViewRepeater$ctl00$ctl01',
            'ctl00$ctl00$MainCPH$MainCPH$EmployeeDDL': self.employee_number
        }
        self.get_timesheet_details(**{**self.current_form, **post_data})

    def get_team_id(self, soup):
        team_id_selection = soup.find(
            'a', {'id': 'ctl00_ctl00_MainCPH_ShiftPlanHL'})
        parsed_url = urlparse(team_id_selection.get('href'))
        self.team_id = parsed_url.query.split('=')[1]

    def get_employee_number(self, soup):

        employee_selection = soup.find('select',
                                       {'class': 'dropwDownAsSelect2'})
        elements_inputs = employee_selection.find_all('option')
        self.employee_dll_class = employee_selection.get('id')
        for element in elements_inputs:

            if not self.username:
                try:
                    if element.get('selected') == 'selected':
                        self.employee_number = element.get('value')
                except TypeError:
                    pass
            else:
                try:
                    if re.search(self.username, element.contents.pop(),
                                 re.MULTILINE):
                        self.employee_number = element.get('value')
                except TypeError:
                    pass

    def get_forms(self, soup):
        post_form_hidden = {}
        post_form_shown = {}

        elements_inputs = soup.find_all('input')

        for element in elements_inputs:
            try:
                if element.get('type') == 'hidden':
                    post_form_hidden.update(
                        {element.get('name'): element.get('value')})
                else:
                    post_form_shown.update(
                        {element.get('name'): element.get('value')})
            except TypeError:
                pass
            pass
        self.current_form = post_form_hidden

    def export_timesheet(self):
        self.get_timesheet_details()
        post_settings = {
            'ctl00$ctl00$MainCPH$MainCPH$DisplayShiftsOverlappedByRequestChB':
            'on',
            '__EVENTTARGET': 'ctl00$ctl00$MainCPH$MainCPH$ExportBtn',
            self.employee_dll_class: self.employee_number
        }
        form_data = {**self.current_form, **post_settings}
        self.browser.request(
            'https://att.tulipize.com/Attendance/AttendanceTimesheet-Edit.aspx',
            form_data)
        return self.browser.current_response.content

    def export_timesheet_to_xlsx(self, filename):
        timesheet_content = self.export_timesheet()
        f = open(filename + 'xlsx', 'wb')
        f.write(timesheet_content)
        f.close()

    def export_timesheet_to_dictionary(self, filename=''):
        """
        Convert the read xls file into JSON.
        :param workbook_url: Fully Qualified URL of the xls file to be read.
        :return: json representation of the workbook.
        """
        timesheet_content = self.export_timesheet()
        if filename:
            workbook = xlrd.open_workbook(filename=filename)
            pass
        else:
            workbook = xlrd.open_workbook(file_contents=timesheet_content)
        workbook_dict = {}
        sheets = workbook.sheets()
        for sheet in sheets:
            workbook_dict[sheet.name] = {}
            columns = sheet.row_values(3)
            rows = []
            for row_index in range(4, sheet.nrows):
                row = sheet.row_values(row_index)
                rows.append(row)
            sheet_data = self.make_json_from_data(columns, rows)
            workbook_dict[sheet.name] = sheet_data
        return workbook_dict

    def make_json_from_data(self, column_names, row_data):
        """
        take column names and row info and merge into a single json object.
        :param data:
        :param json:
        :return:
        """
        row_list = []
        for item in row_data:
            json_obj = {}
            for i in range(0, column_names.__len__()):
                json_obj[column_names[i]] = item[i]
            row_list.append(json_obj)
        return row_list
