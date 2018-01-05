# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.addons.base.ir.ir_mail_server import extract_rfc2822_addresses


class ResUserExtend(models.Model):
    _inherit = 'res.users'

    mail_server = fields.Many2one('ir.mail_server', string=u'Mail Server')


class ir_mail_server(models.Model):
    """发送邮件之前, 根据 smtp_from 查找对应的 smtp 服务器, 如果找不到对应,保留原状."""
    _inherit = "ir.mail_server"

    smtp_host = fields.Char(string='SMTP Server', required=True, help="Hostname or IP of SMTP server",
                            default=lambda self: self.env['ir.config_parameter'].get_param('smtp_sever_host'))

    @api.model
    def send_email(self, message, mail_server_id=None, smtp_server=None, smtp_port=None,
                   smtp_user=None, smtp_password=None, smtp_encryption=None, smtp_debug=False, ):

        smtp_from = message['Return-Path'] or message['From']
        assert smtp_from, "The Return-Path or From header is required for any outbound email"

        # The email's "Envelope From" (Return-Path), and all recipient addresses must only contain ASCII characters.
        from_rfc2822 = extract_rfc2822_addresses(smtp_from)
        assert len(
            from_rfc2822) == 1, "Malformed 'Return-Path' or 'From' address - it may only contain plain ASCII characters"
        smtp_from = from_rfc2822[0]

        #################################################
        # patch: 首先查找 smtp_from 对应的 smtp 服务器
        # 要求 定义 Outgoing Mail Servers 时候, 确保 Description(name) 字段的值 为对应的 邮件发送账户(完整的eMail地址)
        # 本模块以此 为 邮件的发送者 查找 smtp 服务器
        # 需要为系统中 每个可能发送邮件的账户 按以上要求设置一个 服务器
        if self.env.user.mail_server:
            mail_server_ids = self.search([('id', '=', self.env.user.mail_server.id)], order='sequence', limit=1)
            if mail_server_ids:
                mail_server_id = mail_server_ids[0].id

        res = super(ir_mail_server, self).send_email(message,
                                                     mail_server_id,
                                                     smtp_server,
                                                     smtp_port,
                                                     smtp_user,
                                                     smtp_password,
                                                     smtp_encryption,
                                                     smtp_debug
                                                     )
        return res


class AutoSmtpMailMail(models.Model):
    _inherit = 'mail.mail'

    @api.multi
    def send(self, auto_commit=False, raise_exception=False):

        for self_one in self:
            par_list = self.env['res.partner']

            for partner_one in self_one.recipient_ids:
                for child_one in partner_one.child_ids:
                    if child_one.email:
                        par_list += child_one

                self_one.recipient_ids = par_list

        return super(AutoSmtpMailMail, self).send(auto_commit=False, raise_exception=False)

    @api.multi
    def send_get_email_dict(self, partner=None):
        res = super(AutoSmtpMailMail, self).send_get_email_dict(partner)

        res['body'] = (res.get('body') + "<br/><p>" + self.create_uid.signature + "</p>").replace('src="', 'src="' +
                                                                                                  self.sudo().env[
                                                                                                      'ir.config_parameter'].get_param(
                                                                                                      'web.base.url'))

        return res
