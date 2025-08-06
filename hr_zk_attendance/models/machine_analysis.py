from odoo import tools, models, fields,api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    device_id = fields.Char(string='Biometric Device ID')
    is_wfh = fields.Boolean(string="Working from Home",help="Indicates if the employee is working from home")


class ZkMachine(models.Model):
    _name = 'zk.machine.attendance'
    _inherit = 'hr.attendance'
    #
    @api.constrains('check_in', 'check_out', 'employee_id')
    def _check_validity(self):
        pass

    device_id = fields.Char(string='Biometric Device ID')
    punch_type = fields.Selection([
        ('0', 'Check In'),
        ('1', 'Check Out'),
        ('2', 'Break Out'),
        ('3', 'Break In'),
        ('4', 'Overtime In'),
        ('5', 'Overtime Out')
    ], string='Punching Type')

    attendance_type = fields.Selection([
        ('1', 'Finger'),
        ('15', 'Face'),
        ('2', 'Type_2'),
        ('3', 'Password'),
        ('4', 'Card')
    ], string='Category')
    punching_time = fields.Datetime(string='Punching Time')
    address_id = fields.Many2one('res.partner', string='Working Address')


class ReportZkDevice(models.Model):
    _name = 'zk.report.daily.attendance'
    _auto = False
    _order = 'punching_day desc'

    name = fields.Many2one('hr.employee', string='Employee')
    punching_day = fields.Date(string='Date')
    check_in = fields.Datetime(string='Check In')
    check_out = fields.Datetime(string='Check Out')
    address_id = fields.Many2one('res.partner', string='Working Address')
    attendance_type = fields.Selection([
        ('1', 'Finger'),
        ('15', 'Face'),
        ('2', 'Type_2'),
        ('3', 'Password'),
        ('4', 'Card')
    ], string='Category')

    def init(self):
        tools.drop_view_if_exists(self._cr, 'zk_report_daily_attendance')
        query = """
            CREATE OR REPLACE VIEW zk_report_daily_attendance AS (
                WITH ranked_punches AS (
                    SELECT
                        z.id,
                        z.employee_id,
                        z.punching_time,
                        z.address_id,
                        z.attendance_type,
                        ROW_NUMBER() OVER (PARTITION BY z.employee_id, DATE(z.punching_time) ORDER BY z.punching_time) AS row_num
                    FROM zk_machine_attendance z
                    JOIN hr_employee e ON (z.employee_id = e.id)
                ),
                paired_punches AS (
                    SELECT
                        p1.id AS check_in_id,
                        p1.employee_id,
                        p1.punching_time AS check_in,
                        p2.punching_time AS check_out,
                        p1.address_id,
                        p1.attendance_type,
                        EXTRACT(EPOCH FROM (p2.punching_time - p1.punching_time)) AS time_diff
                    FROM
                        ranked_punches p1
                    LEFT JOIN
                        ranked_punches p2
                    ON
                        p1.employee_id = p2.employee_id
                        AND DATE(p1.punching_time) = DATE(p2.punching_time)
                        AND p1.row_num = p2.row_num - 1
                    WHERE
                        p1.row_num % 2 = 1
                        AND (
                            p2.punching_time IS NULL OR
                            EXTRACT(EPOCH FROM (p2.punching_time - p1.punching_time)) >= 20
                        )
                ),
                validated_punches AS (
                    SELECT
                        check_in_id,
                        employee_id,
                        check_in,
                        CASE
                            WHEN check_out IS NOT NULL AND EXTRACT(EPOCH FROM (check_out - check_in)) >= 10 THEN check_out
                            ELSE NULL
                        END AS check_out,
                        address_id,
                        attendance_type,
                        time_diff
                    FROM
                        paired_punches
                ),
                filtered_punches AS (
                    SELECT
                        v.check_in_id,
                        v.employee_id,
                        v.check_in,
                        v.check_out,
                        v.address_id,
                        v.attendance_type,
                        LEAD(v.check_in) OVER (PARTITION BY v.employee_id ORDER BY v.check_in) AS next_check_in
                    FROM
                        validated_punches v
                ),
                final_punches AS (
                    SELECT
                        f.check_in_id,
                        f.employee_id,
                        f.check_in,
                        f.check_out,
                        f.address_id,
                        f.attendance_type
                    FROM
                        filtered_punches f
                    WHERE
                        EXTRACT(EPOCH FROM (f.next_check_in - f.check_in)) > 20
                        OR f.next_check_in IS NULL
                    UNION ALL
                    SELECT
                        z.id AS check_in_id,
                        z.employee_id,
                        z.punching_time AS check_in,
                        NULL AS check_out,
                        z.address_id,
                        z.attendance_type
                    FROM
                        zk_machine_attendance z
                    WHERE
                        NOT EXISTS (
                            SELECT 1
                            FROM filtered_punches f
                            WHERE z.employee_id = f.employee_id
                            AND EXTRACT(EPOCH FROM (z.punching_time - f.check_out)) <= 20
                        )
                )
                SELECT
                    check_in_id AS id,
                    employee_id AS name,
                    DATE(check_in) AS punching_day,
                    check_in,
                    check_out,
                    address_id,
                    attendance_type
                FROM
                    final_punches
            )
        """
        self._cr.execute(query)

    # def init(self):
    #     tools.drop_view_if_exists(self._cr, 'zk_report_daily_attendance')
    #     query = """
    #         CREATE OR REPLACE VIEW zk_report_daily_attendance AS (
    #             WITH ranked_punches AS (
    #                 SELECT
    #                     z.id,
    #                     z.employee_id,
    #                     z.punching_time,
    #                     z.address_id,
    #                     z.attendance_type,
    #                     ROW_NUMBER() OVER (PARTITION BY z.employee_id, DATE(z.punching_time) ORDER BY z.punching_time) AS row_num
    #                 FROM zk_machine_attendance z
    #                 JOIN hr_employee e ON (z.employee_id = e.id)
    #             ),
    #             paired_punches AS (
    #                 SELECT
    #                     p1.id AS check_in_id,
    #                     p1.employee_id,
    #                     p1.punching_time AS check_in,
    #                     p2.punching_time AS check_out,
    #                     p1.address_id,
    #                     p1.attendance_type,
    #                     EXTRACT(EPOCH FROM (p2.punching_time - p1.punching_time)) AS time_diff
    #                 FROM
    #                     ranked_punches p1
    #                 LEFT JOIN
    #                     ranked_punches p2
    #                 ON
    #                     p1.employee_id = p2.employee_id
    #                     AND DATE(p1.punching_time) = DATE(p2.punching_time)
    #                     AND p1.row_num = p2.row_num - 1
    #                 WHERE
    #                     p1.row_num % 2 = 1
    #                     AND (
    #                         p2.punching_time IS NULL OR
    #                         EXTRACT(EPOCH FROM (p2.punching_time - p1.punching_time)) >= 20
    #                     )
    #             ),
    #             validated_punches AS (
    #                 SELECT
    #                     check_in_id,
    #                     employee_id,
    #                     check_in,
    #                     CASE
    #                         WHEN check_out IS NOT NULL AND EXTRACT(EPOCH FROM (check_out - check_in)) >= 10 THEN check_out
    #                         ELSE DATE_TRUNC('day', check_in) + INTERVAL '23:30'  -- Set to fixed 11:30 PM of the same day if check_out is NULL
    #                     END AS check_out,
    #                     address_id,
    #                     attendance_type,
    #                     time_diff
    #                 FROM
    #                     paired_punches
    #             ),
    #             filtered_punches AS (
    #                 SELECT
    #                     v.check_in_id,
    #                     v.employee_id,
    #                     v.check_in,
    #                     v.check_out,
    #                     v.address_id,
    #                     v.attendance_type,
    #                     LEAD(v.check_in) OVER (PARTITION BY v.employee_id ORDER BY v.check_in) AS next_check_in
    #                 FROM
    #                     validated_punches v
    #             ),
    #             final_punches AS (
    #                 SELECT
    #                     f.check_in_id,
    #                     f.employee_id,
    #                     f.check_in,
    #                     f.check_out,
    #                     f.address_id,
    #                     f.attendance_type
    #                 FROM
    #                     filtered_punches f
    #                 WHERE
    #                     EXTRACT(EPOCH FROM (f.next_check_in - f.check_in)) > 20
    #                     OR f.next_check_in IS NULL
    #                 UNION ALL
    #                 SELECT
    #                     z.id AS check_in_id,
    #                     z.employee_id,
    #                     z.punching_time AS check_in,
    #                     DATE_TRUNC('day', z.punching_time) + INTERVAL '3:30' AS check_out,  -- Set check_out to fixed 11:30 PM
    #                     z.address_id,
    #                     z.attendance_type
    #                 FROM
    #                     zk_machine_attendance z
    #                 WHERE
    #                     NOT EXISTS (
    #                         SELECT 1
    #                         FROM filtered_punches f
    #                         WHERE z.employee_id = f.employee_id
    #                         AND EXTRACT(EPOCH FROM (z.punching_time - f.check_out)) <= 20
    #                     )
    #             )
    #             SELECT
    #                 check_in_id AS id,
    #                 employee_id AS name,
    #                 DATE(check_in) AS punching_day,
    #                 check_in,
    #                 check_out,
    #                 address_id,
    #                 attendance_type
    #             FROM
    #                 final_punches
    #         )
    #     """
    #     self._cr.execute(query)
