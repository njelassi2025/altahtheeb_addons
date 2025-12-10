# models/school_trip_request.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import datetime

class SchoolTripRequest(models.Model):
    _name = 'school.trip.request'
    _description = 'نموذج طلب رحلة مدرسية'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    # ------------------------------------------------------------
    # الحقول الأساسية
    # ------------------------------------------------------------
    name = fields.Char(
        string="رقم الطلب", 
        required=True, 
        readonly=True, 
        copy=False, 
        default='New', 
        tracking=True
    )

    trip_type = fields.Selection([
        ('activity', 'رحلة نشاط طلابية'),
        ('evening', 'دورة مسائية'),
        ('other', 'أخرى'),
    ], string="نوع الرحلة", required=True, tracking=True)
    
    bus_line_ids = fields.One2many(
        'school.trip.bus.line',
        'trip_id',
        string="تفاصيل الحافلات",
    )

    date_from = fields.Date(string="تاريخ الرحلة", required=True, tracking=True)
    day_name = fields.Char(string="اليوم", compute="_compute_day_name", store=True)
    students_count = fields.Integer(string="عدد الطلاب", required=True)
    buses_count = fields.Integer(string="عدد الحافلات", required=True)
    direction_from = fields.Char(string="من")
    school_ids = fields.Many2many(
        comodel_name='school.school',
        string='من المدارس',
    )
    
    # ✅ حقل محسوب لعرض أسماء المدارس كنص
    school_names = fields.Char(
        string="أسماء المدارس",
        compute="_compute_school_names",
        store=True
    )

    direction_to = fields.Char(string="الاتجاه إلى", required=True)
    trip_purpose = fields.Char(string="الغرض من الرحلة", required=True)

    stage = fields.Selection([
        ('kg', 'روضه'),
        ('primary', 'الابتدائية'),
        ('middle', 'المتوسطة'),
        ('secondary', 'الثانوية'),
    ], string="المرحلة الدراسية", required=True)

    applicant_name = fields.Char(string="اسم مقدم الطلب", required=True)
    applicant_mobile = fields.Char(string="جوال مقدم الطلب")
    school_leader_name = fields.Char(string="اسم قائد المدرسة", required=True)
    transport_approval = fields.Boolean(string="اعتماد مسؤول النقل", tracking=True)

    state = fields.Selection([
        ('draft', 'مسودة - مقدم الطلب'),
        ('leader', 'قائد المدرسة'),
        ('transport', 'مسؤول النقل'),
        ('approved', 'معتمد نهائياً'),
        ('cancelled', 'ملغي'),
    ], string="الحالة", default='draft', tracking=True)

    # ✅ حقول الربط مع Event Module
    event_id = fields.Many2one(
        'event.event', 
        string="الفعالية المرتبطة", 
        readonly=True, 
        tracking=True,
        copy=False,
        ondelete='restrict'
    )
    event_count = fields.Integer(
        string="عدد الفعاليات", 
        compute="_compute_event_count"
    )

    # ------------------------------------------------------------
    # الحقول المحسوبة
    # ------------------------------------------------------------
    @api.depends('date_from')
    def _compute_day_name(self):
        """تحويل التاريخ إلى اسم اليوم (بالعربية)."""
        days_map = {
            'Saturday': 'السبت', 'Sunday': 'الأحد', 'Monday': 'الإثنين',
            'Tuesday': 'الثلاثاء', 'Wednesday': 'الأربعاء',
            'Thursday': 'الخميس', 'Friday': 'الجمعة'
        }
        for rec in self:
            if rec.date_from:
                day_en = fields.Date.from_string(rec.date_from).strftime('%A')
                rec.day_name = days_map.get(day_en, day_en)
    
    @api.depends('school_ids')
    def _compute_school_names(self):
        """حساب أسماء المدارس كنص للعرض في التقارير"""
        for rec in self:
            if rec.school_ids:
                rec.school_names = ', '.join(rec.school_ids.mapped('name'))
            else:
                rec.school_names = 'غير محدد'

    def _compute_event_count(self):
        """حساب عدد الفعاليات المرتبطة"""
        for rec in self:
            rec.event_count = self.env['event.event'].search_count([
                ('trip_id', '=', rec.id)
            ])

    # ------------------------------------------------------------
    # Actions & Workflows
    # ------------------------------------------------------------
    def action_view_event(self):
        """فتح الفعالية المرتبطة - Smart Button Action"""
        self.ensure_one()
        
        if not self.event_id:
            raise UserError("لا توجد فعالية مرتبطة بهذا الطلب.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'الفعالية المرتبطة',
            'res_model': 'event.event',
            'res_id': self.event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_submit(self):
        """إرسال الطلب إلى قائد المدرسة"""
        for rec in self:
            rec.state = 'leader'
            rec.message_post(body="تم إرسال الطلب إلى قائد المدرسة للمراجعة.")

    def action_leader_approve(self):
        """تحويل الطلب إلى مسؤول النقل"""
        for rec in self:
            rec.state = 'transport'
            rec.message_post(body="تم تحويل الطلب إلى مسؤول النقل للاعتماد النهائي.")

    def action_approve(self):
        """اعتماد نهائي من مسؤول النقل"""
        for rec in self:
            rec.state = 'approved'
            rec.transport_approval = True
            rec.message_post(body="✅ تم اعتماد الطلب نهائيًا من مسؤول النقل.")
    
    def action_cancel(self):
        """إلغاء الطلب"""
        for rec in self:
            # لا نمنع إلغاء الطلب حتى لو كان مرتبطاً بفعالية
            # لكن نحذف الربط مع الفعالية
            if rec.event_id:
                event = rec.event_id
                rec.event_id = False
                event.trip_id = False
                event.message_post(body=f"تم إلغاء طلب الرحلة المرتبط: {rec.name}")
            
            rec.state = 'cancelled'
            rec.message_post(body="تم إلغاء الطلب.")
    
    def action_reset_to_draft(self):
        """إعادة الطلب إلى مسودة"""
        for rec in self:
            rec.state = 'draft'
            rec.transport_approval = False
            rec.message_post(body="تم إعادة الطلب إلى حالة المسودة.")

    # ------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------
    @api.model
    def create(self, vals):
        """توليد رقم تسلسلي تلقائي للطلب."""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'school.trip.request.sequence'
            ) or 'New'
        return super(SchoolTripRequest, self).create(vals)
    
    def write(self, vals):
        """مزامنة التغييرات مع الفعالية المرتبطة"""
        result = super(SchoolTripRequest, self).write(vals)
        
        # مزامنة مع الفعالية إذا وجدت
        for rec in self:
            if rec.event_id:
                event_vals = {}
                
                if 'date_from' in vals:
                    event_vals.update({
                        'date_begin': rec.date_from,
                        'date_end': rec.date_from,
                    })
                
                if 'students_count' in vals:
                    event_vals['seats_max'] = rec.students_count
                
                if 'trip_purpose' in vals:
                    event_vals['name'] = rec.trip_purpose
                
                if event_vals:
                    rec.event_id.write(event_vals)
                    rec.event_id.message_post(body="تم تحديث الفعالية تلقائياً من طلب الرحلة.")
        
        return result
    
    def unlink(self):
        """التعامل مع الفعالية المرتبطة عند حذف الطلب"""
        for rec in self:
            if rec.event_id:
                # فك الربط فقط، لا نحذف الفعالية
                event = rec.event_id
                rec.event_id = False
                event.trip_id = False
                event.message_post(
                    body=f"تم حذف طلب الرحلة المرتبط: {rec.name}"
                )
        return super(SchoolTripRequest, self).unlink()

    # ------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------
    @api.constrains('applicant_mobile')
    def _check_applicant_mobile(self):
        """التحقق من أن رقم الجوال يتكون من 10 أرقام ويبدأ بـ 05."""
        for rec in self:
            if rec.applicant_mobile:
                mobile = rec.applicant_mobile.replace(" ", "").replace("-", "")
                if not (mobile.isdigit() and len(mobile) == 10 and mobile.startswith('05')):
                    raise ValidationError(
                        "رقم الجوال يجب أن يبدأ بـ 05 ويتكون من 10 أرقام صحيحة."
                    )
    
    @api.constrains('students_count', 'buses_count')
    def _check_positive_numbers(self):
        """التحقق من أن الأعداد موجبة"""
        for rec in self:
            if rec.students_count <= 0:
                raise ValidationError("عدد الطلاب يجب أن يكون أكبر من صفر.")
            if rec.buses_count <= 0:
                raise ValidationError("عدد الحافلات يجب أن يكون أكبر من صفر.")


class SchoolTripBusLine(models.Model):
    _name = 'school.trip.bus.line'
    _description = 'تفاصيل الحافلات الخاصة بالرحلة'

    trip_id = fields.Many2one(
        'school.trip.request', 
        string="الرحلة", 
        ondelete='cascade',
        required=True
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle', 
        string="الحافلة", 
        required=True,
        domain="[('vehicle_type', '=', 'bus')]"
    )
    driver_id = fields.Many2one(
        'res.partner', 
        string="السائق"
    )
    driver_mobile = fields.Char(
        string="جوال السائق", 
        related="driver_id.mobile", 
        store=True, 
        readonly=True
    )
    license_plate = fields.Char(
        string="رقم اللوحة", 
        related="vehicle_id.license_plate", 
        store=True, 
        readonly=True
    )
    seats = fields.Integer(
        string="عدد المقاعد", 
        related="vehicle_id.seats", 
        store=True, 
        readonly=True
    )
    notes = fields.Text(string="ملاحظات")

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """عند اختيار المركبة، يتم تعبئة السائق تلقائيًا"""
        if self.vehicle_id and self.vehicle_id.driver_id:
            self.driver_id = self.vehicle_id.driver_id
    
    @api.constrains('vehicle_id', 'trip_id')
    def _check_unique_vehicle(self):
        """التحقق من عدم تكرار نفس الحافلة في نفس الرحلة"""
        for rec in self:
            duplicate = self.search([
                ('id', '!=', rec.id),
                ('trip_id', '=', rec.trip_id.id),
                ('vehicle_id', '=', rec.vehicle_id.id)
            ])
            if duplicate:
                raise ValidationError(
                    f"الحافلة {rec.vehicle_id.name} مضافة بالفعل لهذه الرحلة."
                )