# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-today OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import openerp
from openerp import models, fields, api
from openerp.addons.crm import crm
from openerp.osv import fields, osv
from openerp import tools
from openerp.tools.translate import _
from openerp.tools import html2plaintext
from datetime import datetime, timedelta
import logging
_logger = logging.getLogger(__name__)

AVAILABLE_ACTIONS = [
        ('correction','Corrective Action'),
        ('prevention','Preventive Action'),
        ('replace','Replace Action'),    # New option
        ('discard','Discard Action'),    # New option
    ]

class crm_claim(osv.osv):
    _name = "crm.claim"
    _inherit = "crm.claim"
    _columns = {
        'origin': fields.char('Origin',size=30,readonly=True),
        'products_id': fields.many2many('product.product', 'crm_claim_products', 'crm_claim_id', 'product_id', 'Productos', track_visibility='onchange'),
        'has_check_solution': fields.boolean('has check soluction',readonly=True),
        'type_action': fields.selection(AVAILABLE_ACTIONS, 'Action Type',readonly=True),    # Override required and selections
        'type_id': fields.many2one('crm.claim.type', 'Type'),


        #'product_id' : fields.Many2one('product.product'),
        #'ref': fields.reference('Reference', selection=openerp.addons.base.res.res_request.referencable_models),

    }
    _defaults = {
        'origin': lambda self, cr, uid, context: 'self',
    }

    def create(self, cr, uid, vals, context=None):
        if not 'number_id' in vals or vals['number_id'] == '/':
            if not 'origin' in vals :
                vals['origin'] = 'self'
            vals['number_id'] = vals['origin'] +  str(self.pool.get('ir.sequence').get(cr, uid, 'crm.claim'))
            #vals['number_id'] = vals['origin'] +  str(self.pool.get('ir.sequence').get(cr, uid, 'crm.claim'))
        return super(crm_claim, self).create(cr, uid, vals, context)

    def write(self, cr, uid, ids, vals, context=None):

        if 'stage_id' in vals:
            clm_stg = self.pool.get('crm.claim.stage')
            stage=clm_stg.read(cr, uid, vals['stage_id'], ['user_id','day_to_action_next','action_next','days_to_date_deadline'])

            if 'action_next' in stage and stage['action_next']:
                vals['action_next']=stage['action_next']
                vals['date_action_next']=datetime.today()+timedelta(days=int(stage['day_to_action_next']))
                vals['user_id']=stage['user_id'][0]
            if 'days_to_date_deadline' in stage and stage['days_to_date_deadline']:
                vals['date_deadline']=datetime.today()+timedelta(days=int(stage['days_to_date_deadline']))

        return super(crm_claim, self).write(cr, uid, ids, vals, context=context)


        


    def copy(self, cr, uid, _id, default={}, context=None):
        default.update({
                'number_id': self.pool.get('ir.sequence').get(cr, uid, 'crm.claim'),
            })
        return super(crm_claim, self).copy(cr, uid, _id, default, context)

crm_claim()


class crm_claim_stage(osv.osv):
    _name = "crm.claim.stage"
    _inherit = "crm.claim.stage"
    _columns = {
        'user_id': fields.many2one('res.users', 'Responsible', track_visibility='always'),
        'day_to_action_next': fields.integer('Days to next action'),
        'action_next': fields.char('Next Action'),
        'days_to_date_deadline': fields.char('Date to deadline'),
    }
    _defaults = {
        'day_next_action': lambda self, cr, uid, context: '7',
    }
crm_claim_stage()


class crm_claim_type(osv.osv):
    """ Type of Claim """
    _name = "crm.claim.type"
    _description = "Type of Claim"
    _columns = {
        'name': fields.char('Name', required=True, translate=True),
        'parent_id': fields.many2one('crm.claim.type', 'Type of claim', required=False, ondelete='cascade',
            help="Claim type."),
    }

    """def _find_object_id(self, cr, uid, context=None):
        context = context or {}
        object_id = context.get('object_id', False)
        ids = self.pool.get('ir.model').search(cr, uid, ['|', ('id', '=', object_id), ('model', '=', context.get('object_name', False))])
        return ids and ids[0] or False
    _defaults = {
        'object_id': _find_object_id
    }"""

class claim_from_invoice(osv.osv_memory):
    _name = 'claim.from.invoice'
    _description = 'claim from invoice'

    _columns = {
        'invoice_line' : fields.one2many('account.invoice.line', 'invoice_id', string='Invoice Lines'),
    }

    def claim_from_invoice(self, cr, uid, ids, context=None):
        _logger.info("filoquin ----- ids  : %r", ids)



class view_account_invoice_claims(osv.osv):


    _name = "view.account.invoice.claims"


    _description = "Claim by account invoice"
    _auto = False
    _columns = {
        'id': fields.integer('ID', readonly=True),
        'invoice_id': fields.many2one('account.invoice', 'Invoice'),
        'partner_id': fields.many2one('res.partner', 'Partner'),
        'number': fields.char('number'),
        'name': fields.char('name'),
        'claim_id': fields.many2one('crm.claim', 'Claim'),
        'crm_claim_name': fields.char('Subject'),
        'invoice_line' : fields.one2many('account.invoice.line', 'invoice_id', string='Invoice Lines'),
        #'invoice_line_text_line':fields.function('get_text_lines',  store=False,relation='view.account.invoice.claims' ,
                   # method=True, string='lines',type='char')
        'invoice_line_text': fields.char(compute='_get_text_lines' ,store=False, string="Productos"),
    }

    @api.depends('invoice_line_text','invoice_line')
    def _get_text_lines(self):
        _logger.info("filoquin ----- self  : %r", self)

        for record in self:
            record.invoice_line_text ='sada'


    def prueba(self, cr, uid,ids, context=None):    
        _logger.info("filoquin ----- ids  : %r", ids)
        _logger.info("filoquin ----- context  : %r", context)
              
    def _get_default_warehouse(self, cr, uid, context=None):
        user_obj = self.pool.get('res.users')
        user = user_obj.browse(cr, uid, uid, context=context)
        company_id = user.company_id.id
        wh_obj = self.pool.get('stock.warehouse')
        wh_ids = wh_obj.search(cr, uid,
                               [('company_id', '=', company_id)],
                               context=context)
        if not wh_ids:
            raise orm.except_orm(
                _('Error!'),
                _('There is no warehouse for the current user\'s company.'))
        return wh_ids[0]

    def create(self, cr, uid, vals, context=None):
        _logger.info("filoquin ----- create  : %r", vals)
        #newclaim=self.newclaim( cr, uid, [vals['invoice_id']], context=None) 
        _logger.info("filoquin ----- newclaim  : %r", newclaim)

        pass

    def write(self, cr, uid, vals, context=None):
        _logger.info("filoquin ----- write  : %r", vals)
        pass

    def newclaim(self, cr, uid, ids, context=None):

        res_invoice_id = ids[0]
        claims = self.pool.get('crm.claim').search(cr,uid,
            [('invoice_id', '=', res_invoice_id)],
            context=context)
        if claims :
             return self.open_claim(cr, uid,  claims[0], context=context)



        user_obj = self.pool.get('res.users')
        user = user_obj.browse(cr, uid, uid, context=context)

        invoice = self.pool.get('account.invoice').browse(cr, uid, res_invoice_id, context=context)

        new_claim={'invoice_id': res_invoice_id, 
                   'number_id' : '/',
                   'partner_id': invoice.partner_id.id, 
                   'email_from': invoice.partner_id.email, 
                   'partner_phone': invoice.partner_id.phone,
                   'claim_type': 'customer',
                   'company_id': user.company_id.id,
                   'name': 'prueba ' }

        claim_line_ids=self.add_lines(cr, uid,res_invoice_id,  new_claim['claim_type'],datetime.now,
                                         new_claim['company_id'],context=context)

        new_claim['claim_line_ids']=[(6,0,claim_line_ids)]
        return_id = self.pool.get('crm.claim').create(cr,uid,new_claim)
        return self.open_claim(cr, uid,  return_id, context=context)

    def add_lines(self,cr, uid, invoice_id, claim_type, claim_date, company_id, context=None):
   
        invoice_line_obj = self.pool.get('account.invoice.line')
        invoice_obj = self.pool.get('account.invoice')
        product_obj = self.pool['product.product']
        claim_line_obj = self.pool.get('claim.line')
        company_obj = self.pool['res.company']
        warehouse_obj = self.pool['stock.warehouse']
        invoice_line_ids = invoice_line_obj.search(
            cr, uid,
            [('invoice_id', '=', invoice_id)],
            context=context)
        claim_lines = []
        value = {}

        warehouse_id = self._get_default_warehouse(cr, uid,
                                                       context=context)
        invoice_lines = invoice_line_obj.browse(cr, uid, invoice_line_ids,
                                                context=context)

        def warranty_values(invoice, product):
            values = {}
            try:
                warranty = claim_line_obj._warranty_limit_values(
                    cr, uid, [], invoice,
                    claim_type, product,
                    claim_date, context=context)
            except (InvoiceNoDate, ProductNoSupplier):
                # we don't mind at this point if the warranty can't be
                # computed and we don't want to block the user
                values.update({'guarantee_limit': False, 'warning': False})
            else:
                values.update(warranty)
            company = company_obj.browse(cr, uid, company_id, context=context)
            warehouse = warehouse_obj.browse(cr, uid, warehouse_id,
                                             context=context)
            warranty_address = claim_line_obj._warranty_return_address_values(
                cr, uid, [], product, company,
                warehouse, context=context)
            values.update(warranty_address)
            return values

        for invoice_line in invoice_lines:
            location_dest_id = claim_line_obj.get_destination_location(
                cr, uid, invoice_line.product_id.id,
                warehouse_id, context=context)
            line = {
                'name': invoice_line.name,
                'claim_origine': "none",
                'invoice_line_id': invoice_line.id,
                'product_id': invoice_line.product_id.id,
                'product_returned_quantity': invoice_line.quantity,
                'unit_sale_price': invoice_line.price_unit,
                'location_dest_id': location_dest_id,
                'state': 'draft',
            }
            line.update(warranty_values(invoice_line.invoice_id,invoice_line.product_id))
            line_id=self.pool.get('claim.line').create(cr, uid,line) 
            claim_lines.append(line_id)
        return claim_lines;

    def open_claim(self, cr, uid,  claim_id, context=None):
        ir_model_data = self.pool.get('ir.model.data')
        form_res = ir_model_data.get_object_reference(cr, uid, 'crm_claim', 'crm_case_claims_form_view')
        form_id = form_res and form_res[1] or False
        tree_res = ir_model_data.get_object_reference(cr, uid, 'crm_claim', 'crm_case_claims_tree_view')
        tree_id = tree_res and tree_res[1] or False

        return {
            'name': _('Invoice Claim'),
            'view_type': 'form',
            'view_mode': 'form,tree',
            'res_model': 'crm.claim',
            'res_id': claim_id,
            'view_id': False,
            'target' : 'inline',
            'views': [(form_id, 'form'), (tree_id, 'tree')],
            'type': 'ir.actions.act_window',
        }


    def view_account_invoice_claims(self, cr, uid, ids, context=None):
        invoice_ids = context['active_ids']
        _logger.info("filoquin ----- domain  : %r", invoice_ids)

        if len(invoice_ids) == 0:
            raise osv.except_osv(_('Error!'), _("You should select at least one invoice!!!"))
            return {'type': 'ir.actions.act_window_close'}
        res_invoice = self.read(cr,uid,ids,['id'])
        if not res_invoice[0]['invoice_id']:
            raise osv.except_osv(_('Error!'), _("You should select at least one invoice!!!"))
            return {'type': 'ir.actions.act_window_close'}

        
        res_invoice_id = res_invoice[0]['invoice_id'][0]

        invoice = self.pool.get('account.invoice').browse(cr, uid, res_invoice_id, context=context)
        new_claim={'invoice_id': res_invoice_id, 
                   'partner_id': invoice.partner_id.id, 
                   'email_from': invoice.partner_id.email, 
                   'partner_phone': invoice.partner_id.phone}
        return_id = self.pool.get('crm.claim').write(cr,uid,invoice_ids,new_claim)
        return {}

 
    def init(self, cr):
        tools.sql.drop_view_if_exists(cr, 'view_account_invoice_claims')

        cr.execute(""" 
            create or replace view view_account_invoice_claims as (
                        select ai.id,ai.id as invoice_id, ai.partner_id , ai.number , ai.name  ,cl.id as claim_id, cl.name as  crm_claim_name , 
                        '-' as invoice_line_text 
                        from account_invoice ai 
                        left join crm_claim cl on (ai.id=cl.invoice_id) 
            )
        """)


