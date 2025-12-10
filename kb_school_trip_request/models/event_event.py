# models/event_event.py
# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError

class EventEvent(models.Model):
    _inherit = 'event.event'

    # حقول الربط مع طلبات الرحلات المدرسية
    trip_id = fields.Many2one(
        'school.trip.request', 
        string="طلب الرحلة المدرسية", 
        tracking=True,
        copy=False,
        readonly=True,  # سيتم إنشاؤه تلقائياً
        ondelete='restrict'
    )
    is_school_trip = fields.Boolean(
        string="رحلة مدرسية", 
        compute="_compute_is_school_trip", 
        store=True
    )
    can_create_trip = fields.Boolean(
        string="يمكن إنشاء طلب رحلة",
        compute="_compute_can_create_trip"
    )

    # Computed Fields
    @api.depends('event_type_id')
    def _compute_is_school_trip(self):
        """تحديد إذا كانت الفعالية رحلة مدرسية بناءً على نوع الفعالية"""
        school_trip_type = self.env.ref(
            'kb_school_trip_request.event_type_school_trip', 
            raise_if_not_found=False
        )
        for rec in self:
            rec.is_school_trip = (rec.event_type_id == school_trip_type)
    
    @api.depends('is_school_trip', 'trip_id')
    def _compute_can_create_trip(self):
        """تحديد إمكانية إنشاء طلب رحلة"""
        for rec in self:
            rec.can_create_trip = rec.is_school_trip and not rec.trip_id

    # ------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------
    def action_create_trip_request(self):
        """إنشاء طلب رحلة من الفعالية"""
        self.ensure_one()
        
        # التحقق من أن الفعالية من نوع رحلة مدرسية
        if not self.is_school_trip:
            raise UserError("هذه الفعالية ليست رحلة مدرسية.")
        
        # التحقق من عدم وجود طلب رحلة مرتبط
        if self.trip_id:
            raise UserError("يوجد طلب رحلة مرتبط بالفعل بهذه الفعالية.")
        
        # إعداد قيم طلب الرحلة
        trip_vals = {
            'trip_type': 'activity',
            'date_from': self.date_begin,
            'students_count': int(self.seats_max) if self.seats_max else 0,
            'buses_count': 1,  # قيمة افتراضية
            'direction_to': self.address_id.name if self.address_id else 'غير محدد',
            'trip_purpose': self.name,
            'stage': 'primary',  # قيمة افتراضية
            'applicant_name': self.env.user.name,
            'applicant_mobile': self.env.user.mobile or self.env.user.phone or '',
            'school_leader_name': 'غير محدد',  # يجب تعبئته لاحقاً
            'state': 'draft',
        }
        
        # إنشاء طلب الرحلة
        trip = self.env['school.trip.request'].create(trip_vals)
        
        # ربط طلب الرحلة بالفعالية
        self.trip_id = trip.id
        trip.event_id = self.id
        
        # رسالة في السجل
        self.message_post(
            body=f"تم إنشاء طلب رحلة: <a href='/web#id={trip.id}&model=school.trip.request'>{trip.name}</a>"
        )
        trip.message_post(
            body=f"تم الإنشاء من الفعالية: <a href='/web#id={self.id}&model=event.event'>{self.name}</a>"
        )
        
        # فتح نموذج طلب الرحلة المنشأ
        return {
            'type': 'ir.actions.act_window',
            'name': 'طلب الرحلة المنشأ',
            'res_model': 'school.trip.request',
            'res_id': trip.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_trip(self):
        """فتح طلب الرحلة المرتبط"""
        self.ensure_one()
        
        if not self.trip_id:
            raise UserError("لا يوجد طلب رحلة مرتبط بهذه الفعالية.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'طلب الرحلة المرتبط',
            'res_model': 'school.trip.request',
            'res_id': self.trip_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # ------------------------------------------------------------
    # CRUD Operations
    # ------------------------------------------------------------
    @api.model
    def create(self, vals):
        """
        ✅ عند إنشاء فعالية من نوع رحلة مدرسية، يتم إنشاء طلب رحلة تلقائياً
        """
        event = super(EventEvent, self).create(vals)
        
        # التحقق من نوع الفعالية
        school_trip_type = self.env.ref(
            'kb_school_trip_request.event_type_school_trip', 
            raise_if_not_found=False
        )
        
        # إنشاء طلب رحلة تلقائياً إذا كان نوع الفعالية "رحلة مدرسية"
        if event.event_type_id == school_trip_type and not event.trip_id:
            trip_vals = {
                'trip_type': 'activity',
                'date_from': event.date_begin or fields.Date.today(),
                'students_count': int(event.seats_max) if event.seats_max else 30,
                'buses_count': 1,
                'direction_to': event.address_id.name if event.address_id else 'غير محدد',
                'trip_purpose': event.name or 'رحلة مدرسية',
                'stage': 'primary',
                'applicant_name': event.user_id.name if event.user_id else event.create_uid.name,
                'applicant_mobile': event.user_id.mobile or event.user_id.phone or '',
                'school_leader_name': 'غير محدد',
                'state': 'draft',
            }
            
            try:
                trip = self.env['school.trip.request'].create(trip_vals)
                event.trip_id = trip.id
                trip.event_id = event.id
                
                event.message_post(
                    body=f"✅ تم إنشاء طلب رحلة تلقائياً: <a href='/web#id={trip.id}&model=school.trip.request'>{trip.name}</a>"
                )
            except Exception as e:
                # في حالة فشل إنشاء الطلب، نسجل رسالة فقط ولا نمنع إنشاء الفعالية
                event.message_post(
                    body=f"⚠️ تعذر إنشاء طلب الرحلة تلقائياً: {str(e)}<br/>يمكنك إنشاؤه يدوياً باستخدام زر 'إنشاء طلب رحلة'."
                )
        
        return event

    def write(self, vals):
        """
        تحديث طلب الرحلة المدرسية عند تعديل الفعالية
        """
        result = super(EventEvent, self).write(vals)
        
        for event in self:
            # المزامنة فقط إذا كانت فعالية رحلة مدرسية ومرتبطة بطلب
            if event.trip_id and event.is_school_trip:
                trip_vals = {}
                
                # مزامنة التاريخ
                if 'date_begin' in vals and event.date_begin:
                    trip_vals['date_from'] = event.date_begin
                
                # مزامنة عدد الطلاب
                if 'seats_max' in vals and event.seats_max:
                    trip_vals['students_count'] = int(event.seats_max)
                
                # مزامنة الغرض من الرحلة
                if 'name' in vals and event.name:
                    trip_vals['trip_purpose'] = event.name
                
                # مزامنة الوجهة
                if 'address_id' in vals:
                    if event.address_id:
                        trip_vals['direction_to'] = event.address_id.name
                    else:
                        trip_vals['direction_to'] = 'غير محدد'
                
                # تحديث طلب الرحلة إذا كانت هناك تغييرات
                if trip_vals and event.trip_id.state == 'draft':
                    # نحدث فقط إذا كان الطلب في حالة مسودة
                    event.trip_id.write(trip_vals)
                    event.trip_id.message_post(
                        body="تم تحديث الطلب تلقائياً من الفعالية المرتبطة."
                    )
        
        return result
    
    def unlink(self):
        """التعامل مع طلب الرحلة عند حذف الفعالية"""
        for event in self:
            if event.trip_id:
                # إذا كان طلب الرحلة في حالة مسودة، يمكن حذفه
                if event.trip_id.state == 'draft':
                    trip = event.trip_id
                    event.trip_id = False
                    trip.unlink()
                else:
                    # إذا كان معتمداً، فقط فك الربط
                    event.trip_id.event_id = False
                    event.trip_id.message_post(
                        body=f"تم حذف الفعالية المرتبطة: {event.name}"
                    )
        return super(EventEvent, self).unlink()

    # ------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------
    @api.constrains('trip_id')
    def _check_unique_trip_event(self):
        """التحقق من عدم ربط نفس طلب الرحلة بأكثر من فعالية"""
        for rec in self:
            if rec.trip_id:
                duplicate = self.search([
                    ('id', '!=', rec.id),
                    ('trip_id', '=', rec.trip_id.id)
                ])
                if duplicate:
                    raise ValidationError(
                        f"طلب الرحلة {rec.trip_id.name} مرتبط بالفعل بفعالية أخرى: {duplicate.name}"
                    )