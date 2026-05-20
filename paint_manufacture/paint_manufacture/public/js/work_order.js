/**
 * Paint Manufacture – Work Order extensions
 *
 * Two-stage paint production flow:
 *   Stage 1 — Complete Base Production  (BOM materials → base into WIP)
 *   Stage 2 — Complete Paint Production (base from WIP + packaging → finished SKUs)
 */

const PM_MODULE = "paint_manufacture.paint_manufacture.overrides.work_order";

frappe.ui.form.on("Work Order", {
	refresh(frm) {
		if (frm.doc.pm_is_paint_order) {
			frm.trigger("pm_set_buttons");
			frm.trigger("pm_sync_produced_qty");
			frm.trigger("pm_sync_base_batch");
		}
	},

	pm_is_paint_order(frm) {
		if (frm.doc.pm_is_paint_order) {
			frm.set_value("skip_transfer", 1);
			frm.trigger("pm_sync_produced_qty");
		}
		frm.trigger("pm_set_buttons");
	},

	qty(frm) {
		if (frm.doc.pm_is_paint_order) {
			frm.trigger("pm_sync_produced_qty");
		}
	},

	pm_sync_produced_qty(frm) {
		if (!frm.doc.pm_produced_base_qty) {
			frm.set_value("pm_produced_base_qty", frm.doc.qty);
		}
	},

	pm_sync_base_batch(frm) {
		if (frm.doc.pm_base_batch_no || frm.doc.docstatus !== 1) return;
		frappe.db.get_value(
			"Batch",
			{ reference_doctype: "Work Order", reference_name: frm.doc.name, item: frm.doc.production_item },
			"name",
			(r) => {
				if (r && r.name) {
					frm.set_value("pm_base_batch_no", r.name);
				}
			}
		);
	},

	pm_produced_base_qty(frm) {
		frm.trigger("pm_recalculate_remaining");
	},

	pm_quality_inspection_template(frm) {
		if (!frm.doc.pm_quality_inspection_template || frm.doc.__islocal) return;
		frappe.confirm(
			__("Load parameters from the selected template? This will replace current readings."),
			() => {
				frappe.call({
					method: PM_MODULE + ".pm_load_quality_template",
					args: {
						work_order: frm.doc.name,
						template: frm.doc.pm_quality_inspection_template,
					},
					callback() { frm.reload_doc(); },
				});
			}
		);
	},

	pm_recalculate_remaining(frm) {
		const used = (frm.doc.pm_packaging_items || []).reduce(
			(sum, r) => sum + flt(r.base_qty_used), 0
		);
		frm.set_value("pm_total_base_used", used);
		frm.set_value("pm_remaining_base_qty", flt(frm.doc.pm_produced_base_qty) - used);
	},

	pm_set_buttons(frm) {
		if (!frm.doc.pm_is_paint_order) return;
		if (frm.doc.docstatus !== 1) return;

		// Remove native ERPNext manufacture buttons — paint orders have their own flow.
		frm.remove_custom_button(__("Finish"));
		frm.remove_custom_button(__("Material Consumption"));
		frm.remove_custom_button(__("Start"));
		frm.remove_custom_button(__("Create Pick List"));

		const status = frm.doc.status;
		const baseComplete = !!frm.doc.pm_base_stock_entry;
		const paintComplete = !!frm.doc.pm_paint_stock_entry;

		// ── Not Started ────────────────────────────────────────────────
		if (status === "Not Started") {
			frm.dashboard.add_comment(
				__("Submit the Work Order, then click Start Production to begin the paint production process."),
				"blue", true
			);
			frm.add_custom_button(__("Start Production"), () => {
				frappe.call({
					method: PM_MODULE + ".pm_start_production",
					args: { work_order: frm.doc.name },
					freeze: true,
					freeze_message: __("Starting production…"),
					callback(r) { if (!r.exc) frm.reload_doc(); },
				});
			}, __("Paint Actions")).addClass("btn-primary");
		}

		// ── In Process: Stage 1 pending ────────────────────────────────
		if (status === "In Process" && !baseComplete) {
			frm.dashboard.add_comment(
				__("Enter the Produced Base Qty, then click Complete Base Production. The base will be received into the WIP warehouse before packaging begins."),
				"blue", true
			);
			frm.add_custom_button(__("Complete Base Production"), () => {
				frappe.confirm(
					__("Create a Manufacture Stock Entry for the base paint batch? Raw materials will be consumed and the base will be received into the WIP warehouse."),
					() => {
						frappe.call({
							method: PM_MODULE + ".pm_complete_base_production",
							args: { work_order: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating Base Stock Entry…"),
							callback(r) { if (!r.exc) frm.reload_doc(); },
						});
					}
				);
			}, __("Paint Actions")).addClass("btn-primary");
		}

		// ── In Process: Stage 2 pending ────────────────────────────────
		if (status === "In Process" && baseComplete && !paintComplete) {
			frm.dashboard.add_comment(
				__("Base production complete. Fill in Additional Materials and Packaging Items, then click Complete Paint Production."),
				"green", true
			);
			frm.add_custom_button(__("Complete Paint Production"), () => {
				frappe.confirm(
					__("Create a Manufacture Stock Entry for all packaging materials and finished goods?"),
					() => {
						frappe.call({
							method: PM_MODULE + ".pm_complete_production",
							args: { work_order: frm.doc.name },
							freeze: true,
							freeze_message: __("Creating Paint Stock Entry…"),
							callback(r) { if (!r.exc) frm.reload_doc(); },
						});
					}
				);
			}, __("Paint Actions")).addClass("btn-primary");
		}

		// ── View shortcuts ─────────────────────────────────────────────
		if (frm.doc.pm_base_stock_entry) {
			frm.add_custom_button(
				__("View Base Stock Entry"),
				() => frappe.set_route("Form", "Stock Entry", frm.doc.pm_base_stock_entry),
				__("Paint Actions")
			);
		}

		if (frm.doc.pm_quality_inspection) {
			frm.add_custom_button(
				__("View Quality Inspection"),
				() => frappe.set_route("Form", "Quality Inspection", frm.doc.pm_quality_inspection),
				__("Paint Actions")
			);
		}

		if (frm.doc.pm_paint_stock_entry) {
			frm.add_custom_button(
				__("View Paint Stock Entry"),
				() => frappe.set_route("Form", "Stock Entry", frm.doc.pm_paint_stock_entry),
				__("Paint Actions")
			);
		}
	},
});

// ----------------------------------------------------------------
// PM Packaging Item – live recalc
// ----------------------------------------------------------------

frappe.ui.form.on("PM Packaging Item", {
	packed_qty(frm, cdt, cdn) { _pm_update_base_used(frm, cdt, cdn); },
	container_size_litres(frm, cdt, cdn) { _pm_update_base_used(frm, cdt, cdn); },
});

function _pm_update_base_used(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "base_qty_used",
		flt(row.container_size_litres) * flt(row.packed_qty));
	frm.trigger("pm_recalculate_remaining");
}

// ----------------------------------------------------------------
// PM Additional Material – default source warehouse
// ----------------------------------------------------------------

frappe.ui.form.on("PM Additional Material", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.source_warehouse && frm.doc.source_warehouse) {
			frappe.model.set_value(cdt, cdn, "source_warehouse", frm.doc.source_warehouse);
		}
	},
});

// ----------------------------------------------------------------
// PM Quality Reading – auto-set Accepted / Rejected
// ----------------------------------------------------------------

frappe.ui.form.on("PM Quality Reading", {
	reading_value(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const val = parseFloat(row.reading_value);
		if (isNaN(val)) return;
		const both_zero = flt(row.min_value) === 0 && flt(row.max_value) === 0;
		const in_range = val >= flt(row.min_value) && val <= flt(row.max_value);
		frappe.model.set_value(cdt, cdn, "status", both_zero || in_range ? "Accepted" : "Rejected");
	},
});
