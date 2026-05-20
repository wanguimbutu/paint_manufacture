"""
Paint-manufacture override of the standard ERPNext Work Order.

Two-stage production flow for paint orders:

  Stage 1 — Complete Base Production
    Manufacture SE: BOM raw materials consumed → base paint received in WIP warehouse.
    The base sits in stock so the balance is visible before packaging begins.

  Stage 2 — Complete Paint Production
    Manufacture SE: base consumed from WIP + additional materials + packaging materials
    → finished SKUs received in FG warehouse.
    Any base not used (remaining) stays in the WIP warehouse from Stage 1 automatically.

Status flow:
  Draft → Submit → Not Started → (Start Production) → In Process
  → (Complete Base Production) → In Process [pm_base_stock_entry set]
  → (Complete Paint Production) → Completed

Standard Work Order buttons still work for non-paint orders.

IMPORTANT: All pm_* custom fields are guarded with getattr() so the override
never crashes on Work Orders created before `bench migrate` installed the fields.
"""

import frappe
from frappe import _
from frappe.utils import flt, nowdate

from erpnext.manufacturing.doctype.work_order.work_order import WorkOrder


def _g(doc, field, default=None):
	"""Safe getattr for custom fields that may not exist yet."""
	return getattr(doc, field, default)


class CustomWorkOrder(WorkOrder):
	# ------------------------------------------------------------------
	# Standard lifecycle hooks
	# ------------------------------------------------------------------

	def validate(self):
		super().validate()
		if _g(self, "pm_is_paint_order", 0):
			self._pm_auto_skip_transfer()
			self._pm_calculate_base_used()
			self._pm_calculate_remaining()
		self._pm_normalise_item_amounts()

	def on_submit(self):
		super().on_submit()

	def on_cancel(self):
		super().on_cancel()
		if _g(self, "pm_is_paint_order", 0):
			if _g(self, "pm_paint_stock_entry") or _g(self, "pm_base_stock_entry"):
				self._pm_cancel_stock_entries()

	# ------------------------------------------------------------------
	# Public whitelisted methods (called from JS buttons)
	# ------------------------------------------------------------------

	@frappe.whitelist()
	def pm_start_production(self):
		"""Move the Work Order from Not Started → In Process."""
		if self.status != "Not Started":
			frappe.throw(
				_("Work Order must be in Not Started status to start. Current status: {0}").format(self.status)
			)
		self.db_set("status", "In Process")
		self.db_set("actual_start_date", frappe.utils.now())
		frappe.msgprint(_("Work Order started."), alert=True)

	@frappe.whitelist()
	def pm_complete_base_production(self):
		"""
		Stage 1: consume BOM raw materials and receive the base paint into the
		WIP warehouse.  The Work Order remains In Process; packaging follows next.
		"""
		self._pm_validate_for_base_completion()

		se_name = self._pm_make_base_stock_entry()
		self.db_set("pm_base_stock_entry", se_name)

		frappe.msgprint(
			_("Base production complete. Stock Entry {0} created. You may now fill in Packaging Items and complete paint production.").format(
				frappe.utils.get_link_to_form("Stock Entry", se_name)
			),
			alert=True,
		)
		return se_name

	@frappe.whitelist()
	def pm_complete_production(self):
		"""
		Stage 2: consume base from WIP + additional/packaging materials,
		receive finished SKUs into the FG warehouse, and complete the Work Order.
		"""
		self._pm_validate_for_completion()
		self._pm_calculate_base_used()
		self._pm_calculate_remaining()

		se_name = self._pm_make_stock_entry()
		self.db_set("pm_paint_stock_entry", se_name)
		self.db_set("pm_total_base_used", _g(self, "pm_total_base_used", 0))
		self.db_set("pm_remaining_base_qty", _g(self, "pm_remaining_base_qty", 0))

		if _g(self, "pm_quality_readings"):
			qi_name = self._pm_make_quality_inspection()
			self.db_set("pm_quality_inspection", qi_name)

		self.produced_qty = flt(self.qty)
		self.update_status()

		frappe.msgprint(
			_("Paint production completed. Stock Entry {0} created.").format(
				frappe.utils.get_link_to_form("Stock Entry", se_name)
			),
			alert=True,
		)
		return se_name

	@frappe.whitelist()
	def pm_load_quality_template(self, template=None):
		"""Populate pm_quality_readings from the selected Quality Inspection Template."""
		tmpl = template or _g(self, "pm_quality_inspection_template")
		if not tmpl:
			frappe.throw(_("Please select a Quality Inspection Template first."))
		template_doc = frappe.get_doc("Quality Inspection Template", tmpl)
		self.set("pm_quality_readings", [])
		for row in template_doc.readings:
			self.append(
				"pm_quality_readings",
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

	def _pm_auto_skip_transfer(self):
		"""Paint orders use staged stock entries — no separate WIP transfer step."""
		if not self.skip_transfer:
			self.skip_transfer = 1

	def _pm_calculate_base_used(self):
		total = 0.0
		for row in (_g(self, "pm_packaging_items") or []):
			used = flt(row.container_size_litres) * flt(row.packed_qty)
			row.base_qty_used = used
			total += used
		if hasattr(self, "pm_total_base_used"):
			self.pm_total_base_used = total

	def _pm_calculate_remaining(self):
		if hasattr(self, "pm_remaining_base_qty"):
			self.pm_remaining_base_qty = (
				flt(_g(self, "pm_produced_base_qty", 0))
				- flt(_g(self, "pm_total_base_used", 0))
			)

	def _pm_normalise_item_amounts(self):
		"""Round required_items.amount to avoid floating-point noise on after-submit saves."""
		for item in (self.required_items or []):
			if getattr(item, "amount", None) is not None:
				item.amount = flt(item.amount, 9)

	def _pm_validate_for_base_completion(self):
		if self.status != "In Process":
			frappe.throw(
				_("Base production can only be completed when the Work Order is In Process. Current status: {0}").format(self.status)
			)
		if not flt(_g(self, "pm_produced_base_qty", 0)):
			frappe.throw(_("Please enter the Produced Base Qty before completing base production."))
		existing = _g(self, "pm_base_stock_entry")
		if existing:
			frappe.throw(
				_("Base production is already complete — Stock Entry {0} exists.").format(
					frappe.utils.get_link_to_form("Stock Entry", existing)
				)
			)

	def _pm_validate_for_completion(self):
		if self.status != "In Process":
			frappe.throw(
				_("Paint production can only be completed when the Work Order is In Process. Current status: {0}").format(self.status)
			)
		if not _g(self, "pm_base_stock_entry"):
			frappe.throw(
				_("Please complete base production first before completing paint production.")
			)
		if not (_g(self, "pm_packaging_items") or []):
			frappe.throw(_("Please add at least one row in Packaging Items before completing."))
		existing_se = _g(self, "pm_paint_stock_entry")
		if existing_se:
			frappe.throw(
				_("A Paint Stock Entry {0} already exists for this order.").format(
					frappe.utils.get_link_to_form("Stock Entry", existing_se)
				)
			)

	def _pm_make_base_stock_entry(self):
		"""
		Stage 1 SE: BOM raw materials → base paint into WIP warehouse.
		Standard single-item Manufacture entry — no pm_paint_entry flag needed.
		"""
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Manufacture"
		se.purpose = "Manufacture"
		se.company = self.company
		se.posting_date = nowdate()
		se.bom_no = self.bom_no
		se.fg_completed_qty = flt(_g(self, "pm_produced_base_qty", 0)) or flt(self.qty)

		src_wh = self.source_warehouse
		wip_wh = self.wip_warehouse

		# BOM raw materials consumed from source warehouse
		# WorkOrderItem only has stock_uom (no uom / conversion_factor fields)
		for item in (self.required_items or []):
			qty = flt(item.required_qty)
			if not qty:
				continue
			se.append(
				"items",
				{
					"item_code": item.item_code,
					"qty": qty,
					"uom": item.stock_uom,
					"stock_uom": item.stock_uom,
					"conversion_factor": 1,
					"s_warehouse": item.source_warehouse or src_wh,
					"is_finished_item": 0,
				},
			)

		# Base paint received into WIP warehouse.
		# bom_no on this row makes validate_for_manufacture=True so ERPNext
		# correctly applies Manufacture-specific warehouse rules for all rows.
		base_qty = flt(_g(self, "pm_produced_base_qty", 0)) or flt(self.qty)
		base_uom = frappe.db.get_value("Item", self.production_item, "stock_uom") or "L"
		se.append(
			"items",
			{
				"item_code": self.production_item,
				"qty": base_qty,
				"uom": base_uom,
				"stock_uom": base_uom,
				"conversion_factor": 1,
				"t_warehouse": wip_wh,
				"batch_no": _g(self, "pm_base_batch_no"),
				"is_finished_item": 1,
				"bom_no": self.bom_no,
			},
		)

		se.flags.ignore_permissions = True
		se.save()
		se.submit()
		return se.name

	def _pm_make_stock_entry(self):
		"""
		Stage 2 SE: consume base from WIP + additional/packaging materials,
		receive finished SKUs into FG warehouse.

		The remaining base (produced − used) stays in WIP from Stage 1 naturally —
		no explicit return line is needed.
		"""
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Manufacture"
		se.purpose = "Manufacture"
		se.flags.pm_paint_entry = True  # allows multiple finished SKUs
		se.company = self.company
		se.posting_date = nowdate()
		se.bom_no = self.bom_no

		src_wh = self.source_warehouse
		wip_wh = self.wip_warehouse
		fg_wh = self.fg_warehouse

		# 1. Base paint consumed from WIP (only what was used for packaging).
		# bom_no on this row makes validate_for_manufacture=True so ERPNext
		# correctly applies Manufacture-specific warehouse rules for all rows.
		base_used = flt(_g(self, "pm_total_base_used", 0))
		if base_used > 0 and self.production_item and wip_wh:
			base_uom = frappe.db.get_value("Item", self.production_item, "stock_uom") or "L"
			se.append(
				"items",
				{
					"item_code": self.production_item,
					"qty": base_used,
					"uom": base_uom,
					"stock_uom": base_uom,
					"conversion_factor": 1,
					"s_warehouse": wip_wh,
					"batch_no": _g(self, "pm_base_batch_no"),
					"is_finished_item": 0,
					"bom_no": self.bom_no,
				},
			)

		# 2. Additional materials consumed from source warehouse
		for row in (_g(self, "pm_additional_materials") or []):
			if not flt(row.qty):
				continue
			se.append(
				"items",
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"uom": row.uom,
					"stock_uom": _g(row, "stock_uom") or row.uom,
					"conversion_factor": flt(_g(row, "conversion_factor", 1)) or 1,
					"s_warehouse": _g(row, "source_warehouse") or src_wh,
					"batch_no": _g(row, "batch_no"),
					"is_finished_item": 0,
				},
			)

		# 3. Packaging materials + finished goods per packaged SKU
		for row in (_g(self, "pm_packaging_items") or []):
			if not flt(row.packed_qty):
				continue

			if _g(row, "packaging_material"):
				pkg_qty = flt(_g(row, "packaging_qty", 0)) or flt(row.packed_qty)
				se.append(
					"items",
					{
						"item_code": row.packaging_material,
						"qty": pkg_qty,
						"uom": _g(row, "packaging_uom") or "Nos",
						"stock_uom": _g(row, "packaging_uom") or "Nos",
						"conversion_factor": 1,
						"s_warehouse": src_wh,
						"is_finished_item": 0,
					},
				)

			se.append(
				"items",
				{
					"item_code": row.finished_item,
					"qty": flt(row.packed_qty),
					"uom": _g(row, "uom") or "Nos",
					"stock_uom": _g(row, "uom") or "Nos",
					"conversion_factor": 1,
					"t_warehouse": _g(row, "target_warehouse") or fg_wh,
					"batch_no": _g(row, "batch_no"),
					"is_finished_item": 1,
				},
			)

		se.flags.ignore_permissions = True
		se.save()
		se.submit()
		return se.name

	def _pm_make_quality_inspection(self):
		qi = frappe.new_doc("Quality Inspection")
		qi.inspection_type = "In Process"
		qi.reference_type = "Work Order"
		qi.reference_name = self.name
		qi.item_code = self.production_item
		qi.bom_no = self.bom_no
		qi.company = self.company
		qi.report_date = nowdate()
		qi.quality_inspection_template = _g(self, "pm_quality_inspection_template")

		for row in (_g(self, "pm_quality_readings") or []):
			qi.append(
				"readings",
				{
					"specification": row.parameter,
					"min_value": flt(row.min_value),
					"max_value": flt(row.max_value),
					"reading_value": _g(row, "reading_value"),
					"reading_1": _g(row, "reading_value"),
					"status": _g(row, "status") or "Accepted",
					"manual_inspection": 0,
				},
			)

		qi.flags.ignore_permissions = True
		qi.save()
		return qi.name

	def _pm_cancel_stock_entries(self):
		"""Cancel Stage 2 (paint) before Stage 1 (base) — order matters."""
		for field in ("pm_paint_stock_entry", "pm_base_stock_entry"):
			se_name = _g(self, field)
			if se_name:
				se = frappe.get_doc("Stock Entry", se_name)
				if se.docstatus == 1:
					se.cancel()
		qi_name = _g(self, "pm_quality_inspection")
		if qi_name:
			qi = frappe.get_doc("Quality Inspection", qi_name)
			if qi.docstatus == 1:
				qi.cancel()


# ---------------------------------------------------------------------------
# Module-level whitelisted functions
#
# Frappe resolves short frm.call() names against the *original* doctype
# module (erpnext.manufacturing…), not our override.  Calling these via their
# full dotted path from JS bypasses that lookup and works correctly.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def pm_start_production(work_order):
	doc = frappe.get_doc("Work Order", work_order)
	if doc.status != "Not Started":
		frappe.throw(
			_("Work Order must be Not Started to start. Current status: {0}").format(doc.status)
		)
	doc.db_set("status", "In Process")
	doc.db_set("actual_start_date", frappe.utils.now())

	batch_no = _get_wo_batch(doc)
	if batch_no:
		doc.db_set("pm_base_batch_no", batch_no)
		doc.db_set("custom_work_order_batch", batch_no)

	frappe.msgprint(_("Work Order started."), alert=True)
	return batch_no


@frappe.whitelist()
def pm_complete_base_production(work_order):
	doc = frappe.get_doc("Work Order", work_order)
	return doc.pm_complete_base_production()


@frappe.whitelist()
def pm_complete_production(work_order):
	doc = frappe.get_doc("Work Order", work_order)
	return doc.pm_complete_production()


@frappe.whitelist()
def pm_load_quality_template(work_order, template=None):
	doc = frappe.get_doc("Work Order", work_order)
	doc.pm_load_quality_template(template=template)


def _get_wo_batch(doc):
	"""Return the batch auto-created for this Work Order's production item, if any."""
	return frappe.db.get_value(
		"Batch",
		{"reference_doctype": "Work Order", "reference_name": doc.name, "item": doc.production_item},
		"name",
	)
