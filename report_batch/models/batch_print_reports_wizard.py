import random
from odoo import _, api, fields, models
from odoo.tests.common import Form


class BatchPrintReportsWizard(models.TransientModel):
    _name = "batch.print.reports.wizard"
    _description = "Batch Print Reports Wizard"


    is_collated_by_record = fields.Boolean(string="Collate reports by record?", default=True)
    model_name = fields.Char(string="Model Name")
    res_model = fields.Char(string="Model")
    res_ids = fields.Char(string="Record IDs")
    report_ids = fields.Many2many(
        "ir.actions.report",
        string="Reports",
        domain="[('model', '=', res_model), ('report_type', '=', 'qweb-html'), ('binding_type', '=', 'report'), ('subreport_ids', '=', False)]"
    )

    def generate_batch_report(self) -> dict:
        """
        Create a batch report for the selected reports and generate the batch
        report for the selected records.

        :return:
            A dictionary representation of a report action which loads the batch
            report.
        """
        self.ensure_one()

        # Create a new report template by copying the generic report template
        generic_template_id = self.env.ref("report_batch.generic_report_batch_template")
        template_id = generic_template_id.copy({
            "name": "{}_parent_report_template_{}".format(self.res_model.replace(".", "_"), random.randint(0, 99999)),
            "type": "qweb",
            "model": self.res_model,
            "mode": "primary",
            "arch_base": generic_template_id.arch_base,
        })

        # Create a Parent Report
        report_name = "{} Batch Reports".format(self.model_name)
        parent_report_id = self.env["ir.actions.report"].create({
            "name": report_name,
            "report_type": "qweb-html",
            "model": self.res_model,
            "report_name": template_id.name,
            "print_report_name": report_name,
        })

        # Create Sub-reports for each selected Report
        subreport_obj = self.env["ir.actions.report.subreport"]

        for count, report_id in enumerate(self.report_ids, start=1):
            subreport_obj.create(
                {"parent_report_id": parent_report_id.id, "sequence": 10 * count, "subreport_id": report_id.id}
            )

        # Generate Qweb architecture for the batched report
        parent_report_id._generate_batch_qweb_report(True, self.is_collated_by_record)

        # Remove the batched report from the "Print" dropdown
        parent_report_id.unlink_action()

        # Get records
        res_ids = self.env[self.res_model].search([("id", "in", list(map(int, self.res_ids.split(","))))])

        return parent_report_id.report_action(res_ids.ids)
