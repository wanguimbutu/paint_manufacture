import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class PaintProductionOrder(Document):
	def validate(self):
		self._calculate_required_qtys()
		self._calculate_base_used()
		self._calculate_remaining_base()
		self._auto_set_status()

	def before_submit(self):
		if self.status not in ("Completed",):
			frappe.throw(_("Only a Completed Paint Production Order can be submitted."))

	def on_cancel(self):
		self.status = "Cancelled"
		self._cancel_linked_stock_entry()

	# ------------------------------------------------------------------
	# Public actions (called from JS buttons)
	# ------------------------------------------------------------------

	@frappe.whitelist()
	def start_production(self):
		if self.status != "Draft":
			frappe.throw(_("Production can only be started from Draft status."))
		self._load_bom_items()
		self.status = "In Progress"
		self.save()

	@frappe.whitelist()
	def mark_base_produced(self):
		if self.status != "In Progress":
			frappe.throw(_("Base can only be marked as produced when status is In Progress."))
		if not self.produced_base_qty:
			frappe.throw(_("Please enter the Produced Base Qty before marking as produced."))
		self.status = "Base Produced"
		self._calculate_remaining_base()
		self.save()

	@frappe.whitelist()
	def start_packaging(self):
		if self.status != "Base Produced":
			frappe.throw(_("Packaging can only start after Base is Produced."))
		self.status = "Packaging"
		self.save()

	@frappe.whitelist()
	def complete_production(self):
		"""
		Creates a single Stock Entry covering:
		  - All base raw materials consumed (out)
		  - All additional materials consumed (out)
		  - Packaging materials consumed (out)
		  - Each finished packaged item received (in)
		  - Remaining base returned to WIP warehouse (in)
		Also creates a Quality Inspection if quality readings exist.
		"""
		if self.status not in ("Base Produced", "Packaging"):
			frappe.throw(_("Production can only be completed from Base Produced or Packaging status."))
		if not self.packaging_items:
			frappe.throw(_("Please add at least one Packaging Item before completing."))

		self._calculate_base_used()
		self._calculate_remaining_base()

		stock_entry_name = self._make_stock_entry()
		self.stock_entry = stock_entry_name

		if self.quality_readings:
			qi_name = self._make_quality_inspection()
			self.quality_inspection = qi_name

		self.status = "Completed"
		self.save()
		frappe.msgprint(
			_("Production completed. Stock Entry {0} created.").format(
				frappe.utils.get_link_to_form("Stock Entry", stock_entry_name)
			),
			alert=True,
		)

	@frappe.whitelist()
	def load_quality_template(self):
		"""Populate quality_readings from the selected Quality Inspection Template."""
		if not self.quality_inspection_template:
			frappe.throw(_("Please select a Quality Inspection Template first."))
		template = frappe.get_doc("Quality Inspection Template", self.quality_inspection_template)
		self.quality_readings = []
		for row in template.readings:
			self.append(
				"quality_readings",
				{
					"parameter": row.specification,
					"min_value": flt(row.min_value),
					"max_value": flt(row.max_value),
				},
			)
		self.save()

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _load_bom_items(self):
		"""Fetch BOM items and populate base_raw_materials table."""
		if not self.base_bom:
			return

		bom = frappe.get_doc("BOM", self.base_bom)
		self.base_raw_materials = []

		for item in bom.items:
			required = flt(item.qty) * flt(self.planned_base_qty) / flt(bom.quantity or 1)
			self.append(
				"base_raw_materials",
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"description": item.description,
					"uom": item.uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": flt(item.conversion_factor) or 1,
					"qty_per_unit": flt(item.qty) / flt(bom.quantity or 1),
					"required_qty": required,
					"actual_qty": required,
					"source_warehouse": item.source_warehouse or self.source_warehouse,
				},
			)

	def _calculate_required_qtys(self):
		"""Recompute required_qty in base_raw_materials when planned_base_qty changes."""
		if not self.base_bom or not self.planned_base_qty:
			return

		bom_qty = frappe.db.get_value("BOM", self.base_bom, "quantity") or 1
		for row in self.base_raw_materials:
			if row.qty_per_unit:
				row.required_qty = flt(row.qty_per_unit) * flt(self.planned_base_qty)
				if not row.actual_qty:
					row.actual_qty = row.required_qty

	def _calculate_base_used(self):
		"""Compute base_qty_used per packaging row and total_base_used."""
		total = 0.0
		for row in self.packaging_items:
			used = flt(row.container_size_litres) * flt(row.packed_qty)
			row.base_qty_used = used
			total += used
		self.total_base_used = total

	def _calculate_remaining_base(self):
		self.remaining_base_qty = flt(self.produced_base_qty) - flt(self.total_base_used)

	def _auto_set_status(self):
		if self.status in ("Completed", "Cancelled"):
			return
		if not self.status:
			self.status = "Draft"

	def _make_stock_entry(self):
		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.company = self.company
		se.posting_date = nowdate()
		se.paint_production_order = self.name

		source_wh = self.source_warehouse
		wip_wh = self.wip_warehouse
		fg_wh = self.fg_warehouse

		# --- Consume base raw materials ---
		for row in self.base_raw_materials:
			qty = flt(row.actual_qty) or flt(row.required_qty)
			if not qty:
				continue
			se.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": qty,
					"uom": row.uom,
					"stock_uom": row.stock_uom or row.uom,
					"conversion_factor": flt(row.conversion_factor) or 1,
					"s_warehouse": row.source_warehouse or source_wh,
					"batch_no": row.batch_no,
					"is_finished_item": 0,
				},
			)

		# --- Consume additional materials ---
		for row in self.additional_materials:
			if not flt(row.qty):
				continue
			se.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"uom": row.uom,
					"stock_uom": row.stock_uom or row.uom,
					"conversion_factor": flt(row.conversion_factor) or 1,
					"s_warehouse": row.source_warehouse or source_wh,
					"batch_no": row.batch_no,
					"is_finished_item": 0,
				},
			)

		# --- Consume packaging materials & receive finished goods ---
		for row in self.packaging_items:
			if not flt(row.packed_qty):
				continue

			# Packaging material (e.g. tins/labels)
			if row.packaging_material:
				pkg_qty = flt(row.packaging_qty) or flt(row.packed_qty)
				se.append(
					"items",
					{
						"item_code": row.packaging_material,
						"qty": pkg_qty,
						"uom": row.packaging_uom,
						"stock_uom": row.packaging_uom,
						"conversion_factor": 1,
						"s_warehouse": source_wh,
						"is_finished_item": 0,
					},
				)

			# Finished painted goods received into FG warehouse
			se.append(
				"items",
				{
					"item_code": row.finished_item,
					"qty": flt(row.packed_qty),
					"uom": row.uom,
					"stock_uom": row.uom,
					"conversion_factor": 1,
					"t_warehouse": row.target_warehouse or fg_wh,
					"batch_no": row.batch_no,
					"is_finished_item": 1,
				},
			)

		# --- Return remaining base to WIP/base stock ---
		if flt(self.remaining_base_qty) > 0 and self.base_item and wip_wh:
			se.append(
				"items",
				{
					"item_code": self.base_item,
					"qty": flt(self.remaining_base_qty),
					"uom": self.base_uom,
					"stock_uom": self.base_uom,
					"conversion_factor": 1,
					"t_warehouse": wip_wh,
					"batch_no": self.base_batch_no,
					"is_finished_item": 0,
					"remarks": _("Remaining base returned to stock"),
				},
			)

		se.flags.ignore_permissions = True
		se.save()
		se.submit()
		return se.name

	def _make_quality_inspection(self):
		qi = frappe.new_doc("Quality Inspection")
		qi.inspection_type = "In Process"
		qi.reference_type = "Paint Production Order"
		qi.reference_name = self.name
		qi.item_code = self.base_item
		qi.bom_no = self.base_bom
		qi.company = self.company
		qi.report_date = nowdate()
		qi.quality_inspection_template = self.quality_inspection_template

		for row in self.quality_readings:
			qi.append(
				"readings",
				{
					"specification": row.parameter,
					"min_value": flt(row.min_value),
					"max_value": flt(row.max_value),
					"reading_value": row.reading_value,
					"reading_1": row.reading_value,
					"status": row.status or "Accepted",
					"manual_inspection": 0,
				},
			)

		qi.flags.ignore_permissions = True
		qi.save()
		return qi.name

	def _cancel_linked_stock_entry(self):
		if self.stock_entry:
			se = frappe.get_doc("Stock Entry", self.stock_entry)
			if se.docstatus == 1:
				se.cancel()
		if self.quality_inspection:
			qi = frappe.get_doc("Quality Inspection", self.quality_inspection)
			if qi.docstatus == 1:
				qi.cancel()


@frappe.whitelist()
def create_work_order_from_plan(plan_name):
	"""
	Create a standard ERPNext Work Order from a Paint Production Order (planning worksheet).
	The Work Order is pre-configured as a Paint Order with skip_transfer=1 and all
	the paint-specific tables copied over.
	"""
	plan = frappe.get_doc("Paint Production Order", plan_name)
	if plan.work_order:
		frappe.throw(
			_("A Work Order {0} is already linked to this plan.").format(
				frappe.utils.get_link_to_form("Work Order", plan.work_order)
			)
		)

	wo = frappe.new_doc("Work Order")
	wo.production_item = plan.base_item
	wo.bom_no = plan.base_bom
	wo.qty = flt(plan.planned_base_qty)
	wo.company = plan.company
	wo.source_warehouse = plan.source_warehouse
	wo.wip_warehouse = plan.wip_warehouse
	wo.fg_warehouse = plan.fg_warehouse
	wo.planned_start_date = plan.production_date
	wo.skip_transfer = 1
	wo.pm_is_paint_order = 1

	# Copy additional materials
	for row in plan.additional_materials:
		wo.append(
			"pm_additional_materials",
			{
				"item_code": row.item_code,
				"uom": row.uom,
				"qty": flt(row.qty),
				"source_warehouse": row.source_warehouse or plan.source_warehouse,
				"notes": row.notes,
			},
		)

	# Copy packaging items
	for row in plan.packaging_items:
		wo.append(
			"pm_packaging_items",
			{
				"finished_item": row.finished_item,
				"container_size_litres": flt(row.container_size_litres),
				"packed_qty": flt(row.packed_qty),
				"target_warehouse": row.target_warehouse or plan.fg_warehouse,
				"packaging_material": row.packaging_material,
				"packaging_qty": flt(row.packaging_qty),
			},
		)

	# Copy quality readings
	for row in plan.quality_readings:
		wo.append(
			"pm_quality_readings",
			{
				"parameter": row.parameter,
				"min_value": flt(row.min_value),
				"max_value": flt(row.max_value),
			},
		)

	wo.pm_quality_inspection_template = plan.quality_inspection_template
	wo.flags.ignore_permissions = True
	wo.insert()

	plan.db_set("work_order", wo.name)
	frappe.msgprint(
		_("Work Order {0} created.").format(
			frappe.utils.get_link_to_form("Work Order", wo.name)
		),
		alert=True,
	)
	return wo.name


@frappe.whitelist()
def get_bom_items(bom_no, planned_qty):
	"""Return BOM items scaled to planned_qty for client-side preview."""
	if not bom_no:
		return []
	bom = frappe.get_doc("BOM", bom_no)
	bom_qty = flt(bom.quantity) or 1
	scale = flt(planned_qty) / bom_qty
	rows = []
	for item in bom.items:
		rows.append(
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"description": item.description,
				"uom": item.uom,
				"stock_uom": item.stock_uom,
				"conversion_factor": flt(item.conversion_factor) or 1,
				"qty_per_unit": flt(item.qty) / bom_qty,
				"required_qty": flt(item.qty) * scale,
				"actual_qty": flt(item.qty) * scale,
				"source_warehouse": item.source_warehouse,
			}
		)
	return rows
