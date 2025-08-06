import logging
from struct import unpack

import pytz
from odoo.exceptions import UserError, ValidationError
from zk import ZK

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    device_id = fields.Char(string='Biometric Device ID')
    attendance_date = fields.Date(string="Attendance Date")


class ZkMachine(models.Model):
    _name = 'zk.machine'

    name = fields.Char(string='Machine IP', required=True)
    port_no = fields.Integer(string='Port No', required=True)
    address_id = fields.Many2one('res.partner', string='Working Address')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.user.company_id.id)

    def device_connect(self, zk):
        try:
            conn = zk.connect()
            return conn
        except:
            return False

    def clear_attendance(self):
        for info in self:
            try:
                machine_ip = info.name
                zk_port = info.port_no
                timeout = 30
                try:
                    zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
                except NameError:
                    raise UserError(_("Please install it with 'pip3 install pyzk'."))
                conn = self.device_connect(zk)
                if conn:
                    conn.enable_device()
                    clear_data = zk.get_attendance()
                    if clear_data:
                        self._cr.execute("""delete from zk_machine_attendance""")
                        conn.disconnect()
                        raise UserError(_('Attendance Records Deleted.'))
                    else:
                        raise UserError(_('Unable to clear Attendance log. Are you sure attendance log is not empty.'))
                else:
                    raise UserError(
                        _('Unable to connect to Attendance Device. Please use Test Connection button to verify.'))
            except:
                raise ValidationError(
                    'Unable to clear Attendance log. Are you sure attendance device is connected & record is not empty.')

    def getSizeUser(self, zk):
        command = unpack('HHHH', zk.data_recv[:8])[0]
        if command == CMD_PREPARE_DATA:
            size = unpack('I', zk.data_recv[8:12])[0]
            print("size", size)
            return size
        else:
            return False

    def zkgetuser(self, zk):
        try:
            users = zk.get_users()
            print(users)
            return users
        except:
            return False

    @api.model
    def cron_download(self):
        machines = self.env['zk.machine'].search([])
        for machine in machines:
            machine.download_attendance()

    def download_attendance(self):
        _logger.info("++++++++++++Cron Executed++++++++++++++++++++++")
        zk_attendance = self.env['zk.machine.attendance']
        att_obj = self.env['hr.attendance']
        for info in self:
            machine_ip = info.name
            zk_port = info.port_no
            timeout = 15
            try:
                zk = ZK(machine_ip, port=zk_port, timeout=timeout, password=0, force_udp=False, ommit_ping=False)
            except NameError:
                raise UserError(_("Pyzk module not Found. Please install it with 'pip3 install pyzk'."))
            conn = self.device_connect(zk)
            if conn:
                try:
                    user = conn.get_users()
                except:
                    user = False
                try:
                    attendance = conn.get_attendance()
                except:
                    attendance = False
                if attendance:
                    # raise ValidationError('Connected')
                    for each in attendance:
                        atten_time = each.timestamp
                        local_tz = pytz.timezone(self.env.user.partner_id.tz or 'GMT')
                        local_dt = local_tz.localize(atten_time, is_dst=None)
                        utc_dt = local_dt.astimezone(pytz.utc)
                        atten_time = utc_dt.strftime("%Y-%m-%d %H:%M:%S")
                        # atten_time=fields.Datetime.to_string(atten_time)
                        if user:
                            for uid in user:
                                if uid.user_id == each.user_id:
                                    # get_user_id = self.env['hr.employee'].search([('device_id', '=', each.user_id)])
                                    # if get_user_id:
                                    #     duplicate_atten_ids = zk_attendance.search(
                                    #         [('device_id', '=', each.user_id), ('punching_time', '=', atten_time)])
                                    #     if duplicate_atten_ids:
                                    #         continue
                                    #     else:
                                    #         zk_attendance.create({
                                    #             'employee_id': get_user_id.id,
                                    #             'device_id': each.user_id,
                                    #             'attendance_type': str(each.status),
                                    #             'punch_type': str(each.punch),
                                    #             'punching_time': atten_time,
                                    #             'address_id': info.address_id.id
                                    #         })

                                    get_user_ids = self.env['hr.employee'].search([('device_id', '=', each.user_id)])
                                    if get_user_ids:
                                        for get_user_id in get_user_ids:
                                            duplicate_atten_ids = zk_attendance.search(
                                                [('device_id', '=', each.user_id), ('punching_time', '=', atten_time)])
                                            if duplicate_atten_ids:
                                                continue
                                            else:
                                                zk_attendance.create({
                                                    'employee_id': get_user_id.id,
                                                    'device_id': each.user_id,
                                                    'attendance_type': str(each.status),
                                                    'punch_type': str(each.punch),
                                                    'punching_time': atten_time,
                                                    'address_id': info.address_id.id
                                                })

                                    else:
                                        employee = self.env['hr.employee'].create(
                                            {'device_id': each.user_id, 'name': uid.name})
                                        zk_attendance.create({
                                            'employee_id': employee.id,
                                            'device_id': each.user_id,
                                            'attendance_type': str(each.status),
                                            'punch_type': str(each.punch),
                                            'punching_time': atten_time,
                                            'address_id': info.address_id.id
                                        })
                                        att_obj.create({'employee_id': employee.id, 'check_in': atten_time})
                                else:
                                    pass
                    conn.disconnect()
                    return True
                else:
                    raise UserError(_('Unable to get the attendance log, please try again later.'))
            else:
                raise UserError(_('Unable to connect, please check the parameters and network connections.'))

    def create_hr_attendance_records(self):
        zk_attendance = self.env['zk.machine.attendance']
        att_obj = self.env['hr.attendance']

        attendance_data = {}
        for attendance in zk_attendance.search([]):
            employee_id = attendance.employee_id.id
            punch_date = fields.Date.to_date(attendance.punching_time)
            attendance_type = attendance.attendance_type
            key = (employee_id, punch_date, attendance_type)
            if key not in attendance_data:
                attendance_data[key] = []
            attendance_data[key].append(attendance)

        for (employee_id, punch_date, attendance_type), punches in attendance_data.items():
            punches.sort(key=lambda x: x.punching_time)
            check_in_time = punches[0].punching_time
            check_out_time = punches[-1].punching_time

            existing_attendance = att_obj.search([
                ('employee_id', '=', employee_id),
                ('attendance_date', '=', punch_date)
            ], limit=1)

            if existing_attendance:
                new_check_out_time = max(existing_attendance.check_out, check_out_time)
                existing_attendance.write({
                    'check_out': new_check_out_time
                })
            else:
                att_obj.create({
                    'employee_id': employee_id,
                    'check_in': check_in_time,
                    'check_out': check_out_time,
                    'attendance_date': punch_date
                })

    # def create_hr_attendance_records(self):
    #     zk_attendance = self.env['zk.machine.attendance']
    #     att_obj = self.env['hr.attendance']
    #
    #     # attendance by employee and date
    #     attendance_data = {}
    #     for attendance in zk_attendance.search([]):
    #         employee_id = attendance.employee_id.id
    #         punch_date = fields.Date.to_date(attendance.punching_time)
    #         if (employee_id, punch_date) not in attendance_data:
    #             attendance_data[(employee_id, punch_date)] = []
    #         attendance_data[(employee_id, punch_date)].append(attendance)
    #
    #     for (employee_id, punch_date), punches in attendance_data.items():
    #         punches.sort(key=lambda x: x.punching_time)
    #
    #         check_in_time = punches[0].punching_time
    #         check_out_time = punches[-1].punching_time
    #
    #         att_obj.create({
    #             'employee_id': employee_id,
    #             'check_in': check_in_time,
    #             'check_out': check_out_time,
    #             'attendance_date': punch_date
    #         })

    # def create_hr_attendance_records(self):
    #     zk_attendance = self.env['zk.machine.attendance']
    #     att_obj = self.env['hr.attendance']
    #     emp_obj = self.env['hr.employee']
    #
    #     attendance_data = {}
    #     for attendance in zk_attendance.search([]):
    #         employee_id = attendance.employee_id.id
    #         punch_date = fields.Date.to_date(attendance.punching_time)
    #         attendance_type = attendance.attendance_type
    #         key = (employee_id, punch_date, attendance_type)
    #         if key not in attendance_data:
    #             attendance_data[key] = []
    #         attendance_data[key].append(attendance)
    #
    #     for (employee_id, punch_date, attendance_type), punches in attendance_data.items():
    #         if att_obj.search([('employee_id', '=', employee_id), ('check_in', '=', punches[0].punching_time)]):
    #             continue
    #
    #         punches.sort(key=lambda x: x.punching_time)
    #
    #         check_in_time = punches[0].punching_time
    #         check_out_time = punches[-1].punching_time
    #
    #         employee = emp_obj.search([('device_id', '=', punches[0].device_id)])
    #         if not employee:
    #             employee = emp_obj.create({'device_id': punches[0].device_id, 'name': punches[0].employee_name})
    #         else:
    #             employee = employee[0]
    #
    #         att_obj.create({
    #             'employee_id': employee.id,
    #             'check_in': check_in_time,
    #             'check_out': check_out_time,
    #             'attendance_date': punch_date
    #         })
    #
