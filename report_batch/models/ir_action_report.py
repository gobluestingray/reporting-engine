# Copyright (C) 2019 IBM Corp.
# Copyright (C) 2019 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import random

from odoo import api, fields, models


class IrActionsReportSubreport(models.Model):
    _name = "ir.actions.report.subreport"
    _description = "Report Subreport"
    _order = "sequence"

    parent_report_id = fields.Many2one("ir.actions.report", ondelete="cascade")
    sequence = fields.Integer(default=10)
    model = fields.Char(related="parent_report_id.model")
    subreport_id = fields.Many2one(
        "ir.actions.report", string="Subreport", required=True
    )


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    subreport_ids = fields.One2many("ir.actions.report.subreport", "parent_report_id")

    def generate_top_part(self, collate_by_record=False):
        if collate_by_record:
            return (
            """<?xml version="1.0"?>\n\t<t t-name="%s">\n\t\t<t t-call="web.html_container">\n\t\t\t<div class="instructions">
	<a href="#" onclick="document.getElementById('editable_header').contentEditable = (document.getElementById('editable_header').isContentEditable ? 'false' : 'true')">Toggle Editing</a>
	<a target="_blank" href="http://support.metricwise.net/entries/20525276-printer-margins-for-bar-code-label-sheets">Instructions on Setting up Label Printing</a>
</div><div id="editable_header" style="height:100px"></div>
            \n\t\t\t<t t-foreach="docs" t-as="doc">\n\t\t\t
        """
            % self.report_name
        )
        return (
            """<?xml version="1.0"?>\n\t<t t-name="%s">\n\t
        """
            % self.report_name
        )

    def generate_bottom_part(self, collate_by_record=False):
        if collate_by_record:
            return """\n\t\t\t</t>\n\t\t</t>
        \n\t\t</t>\n\t\t"""
        return """\n
        \t\t</t>\n\t\t"""

    def generate_custom_content(self, report_name, collate_by_record=False):
        if collate_by_record:
            return (
                """\n
            \t<t t-call="%s" t-lang="doc.partner_id.lang"/>"""
                % report_name
            )
        return (
            """\n
        \t<t t-call="%s"/>"""
            % report_name
        )

    def _generate_batch_qweb_report(self, update_batch_qweb=False, collate_by_record=False):
        report_name = self.report_name
        if "." in report_name:
            module = self.report_name.split(".")[0]
            report_name = self.report_name.split(".")[1]
        else:
            # Generate random number to avoid IntegrityError
            module = random.randint(1, 1000000)
            self.report_name = "{}.{}".format(module, report_name)
        if self.subreport_ids:
            if update_batch_qweb:
                report_name = self.report_name.split(".")[1]
                # Delete old Qweb batch report
                model_data = self.env["ir.model.data"].search(
                    [("res_id", "=", self.id)]
                )
                model_data.unlink()
                ui_view = self.env["ir.ui.view"].search([("name", "=", report_name)])
                ui_view.unlink()
            template_header = self.generate_top_part(True)
            template_footer = self.generate_bottom_part(True)
            template_content = ""

            for subreport in self.subreport_ids:
                if collate_by_record:
                    view_id = self.env["ir.ui.view"].search([("name", "=", subreport.subreport_id.report_name.split(".")[1])], limit=1)
                    document_name = view_id.arch.split('t-call="')[2].split('"')[0]
                    template_content += self.generate_custom_content(document_name, True)
                else:
                    template_content += self.generate_custom_content(
                        subreport.subreport_id.report_name
                    )
            data = "{}{}{}".format(template_header, template_content, template_footer)
            ui_view = self.env["ir.ui.view"].create(
                {
                    "name": report_name,
                    "type": "qweb",
                    "model": self.model,
                    "mode": "primary",
                    "arch_base": data,
                }
            )
            self.env["ir.model.data"].create(
                {
                    "module": module,
                    "name": report_name,
                    "res_id": ui_view.id,
                    "model": "ir.ui.view",
                }
            )
            # Register batch report option
            if not self.binding_model_id:
                self.create_action()
        return True

    @api.model
    def create(self, vals):
        res = super(IrActionsReport, self).create(vals)
        for report in res:
            report._generate_batch_qweb_report()
        return res

    def write(self, vals):
        res = super(IrActionsReport, self).write(vals)
        if "subreport_ids" in vals or "model" in vals:
            for report in self:
                report._generate_batch_qweb_report(update_batch_qweb=True)
        return res

    @api.model
    def batch_print_reports(self, record_ids: models.Model) -> dict:
        """
        Launch the Batch Print Records Wizard.

        :param record_ids: The records to be converted into reports.
        :return:
            A dictionary representation of a Window Action which will load the
            Batch Print Records Wizard.
        """
        action = self.env.ref("report_batch.action_batch_print_reports_wizard").read()[0]

        # Get all Qweb reports (except for "parent" reports with sub-reports)
        # for the records' model
        report_ids = self.env["ir.actions.report"].search([
            ("report_type", "=", "qweb-html"),
            ("model", "=", record_ids._name),
            ("binding_type", "=", "report"),
            ("subreport_ids", "=", False),
        ])

        # Convert a list of ID integers into a single string of comma-separated
        # IDs in order to be stored in a Char field
        str_ids = ",".join([str(id) for id in record_ids.ids])

        # Add defaults for the wizard
        action["context"] = {
            "default_model_name": record_ids._description,
            "default_res_model": record_ids._name,
            "default_res_ids": str_ids,
            "default_report_ids": report_ids.ids,
        }

        return action
