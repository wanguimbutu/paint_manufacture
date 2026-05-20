frappe.ui.form.on("Paint Production Order", {
	refresh(frm) {
		frm.trigger("set_action_buttons");
		frm.trigger("set_field_states");
	},

	// ----------------------------------------------------------------
	// BOM / qty changes
	// ----------------------------------------------------------------

	base_bom(frm) {
		if (frm.doc.base_bom && frm.doc.planned_base_qty) {
			frm.trigger("reload_bom_items");
		}
	},

	planned_base_qty(frm) {
		if (frm.doc.base_bom && frm.doc.planned_base_qty) {
			frm.trigger("recalculate_required_qtys");
		}
	},

	reload_bom_items(frm) {
		frappe.call({
			method: "paint_manufacture.paint_manufacture.doctype.paint_production_order.paint_production_order.get_bom_items",
			args: {
				bom_no: frm.doc.base_bom,
				planned_qty: frm.doc.planned_base_qty || 1,
			},
			callback(r) {
				if (!r.message) return;
				frm.clear_table("base_raw_materials");
				r.message.forEach((row) => frm.add_child("base_raw_materials", row));
				frm.refresh_field("base_raw_materials");
			},
		});
	},

	recalculate_required_qtys(frm) {
		(frm.doc.base_raw_materials || []).forEach((row) => {
			if (row.qty_per_unit) {
				frappe.model.set_value(
					row.doctype,
					row.name,
					"required_qty",
					flt(row.qty_per_unit) * flt(frm.doc.planned_base_qty)
				);
			}
		});
	},

	// ----------------------------------------------------------------
	// Base result
	// ----------------------------------------------------------------

	produced_base_qty(frm) {
		frm.trigger("recalculate_remaining");
	},

	recalculate_remaining(frm) {
		const used = (frm.doc.packaging_items || []).reduce(
			(s, r) => s + flt(r.base_qty_used),
			0
		);
		frm.set_value("total_base_used", used);
		frm.set_value(
			"remaining_base_qty",
			flt(frm.doc.produced_base_qty) - used
		);
	},

	// ----------------------------------------------------------------
	// Quality template
	// ----------------------------------------------------------------

	quality_inspection_template(frm) {
		if (frm.doc.quality_inspection_template && !frm.doc.__islocal) {
			frappe.confirm(
				__("Load parameters from template? This will replace current readings."),
				() => frm.call("load_quality_template").then(() => frm.refresh())
			);
		}
	},

	// ----------------------------------------------------------------
	// Action buttons based on status
	// ----------------------------------------------------------------

	set_action_buttons(frm) {
		frm.clear_custom_buttons();

		if (frm.doc.docstatus !== 0) return;

		const status = frm.doc.status;

		if (status === "Draft") {
			frm.add_custom_button(__("Start Production"), () => {
				if (!frm.doc.base_bom) {
					frappe.msgprint(__("Please set the Base BOM before starting."));
					return;
				}
				if (!frm.doc.planned_base_qty) {
					frappe.msgprint(__("Please enter Planned Base Qty before starting."));
					return;
				}
				frm.call("start_production").then(() => frm.refresh());
			}, __("Actions"));
		}

		if (status === "In Progress") {
			frm.add_custom_button(__("Mark Base Produced"), () => {
				if (!frm.doc.produced_base_qty) {
					frappe.msgprint(__("Enter Produced Base Qty first."));
					return;
				}
				frm.call("mark_base_produced").then(() => frm.refresh());
			}, __("Actions"));
		}

		if (status === "Base Produced") {
			frm.add_custom_button(__("Start Packaging"), () => {
				frm.call("start_packaging").then(() => frm.refresh());
			}, __("Actions"));
		}

		if (["Base Produced", "Packaging"].includes(status)) {
			frm.add_custom_button(__("Complete Production"), () => {
				frappe.confirm(
					__("This will create a Stock Entry and finalise the batch. Proceed?"),
					() => {
						frm.call("complete_production").then(() => frm.refresh());
					}
				);
			}, __("Actions")).addClass("btn-primary");
		}

		if (["Completed"].includes(status) && frm.doc.stock_entry) {
			frm.add_custom_button(__("View Stock Entry"), () => {
				frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry);
			});
		}

		// Allow creating a linked Work Order from the planning worksheet
		if (!frm.doc.work_order && !["Completed", "Cancelled"].includes(status)) {
			frm.add_custom_button(__("Create Work Order"), () => {
				frappe.confirm(
					__("Create a standard Work Order from this plan? The Work Order will be pre-configured as a Paint Order."),
					() => {
						frappe.call({
							method: "paint_manufacture.paint_manufacture.doctype.paint_production_order.paint_production_order.create_work_order_from_plan",
							args: { plan_name: frm.doc.name },
							freeze: true,
							callback(r) {
								if (!r.exc) {
									frm.reload_doc();
									if (r.message) {
										frappe.set_route("Form", "Work Order", r.message);
									}
								}
							},
						});
					}
				);
			}, __("Actions"));
		}

		if (frm.doc.work_order) {
			frm.add_custom_button(__("Open Work Order"), () => {
				frappe.set_route("Form", "Work Order", frm.doc.work_order);
			});
		}
	},

	set_field_states(frm) {
		const status = frm.doc.status;
		const is_draft = status === "Draft";
		const is_completed = frm.doc.docstatus === 1 || status === "Completed" || status === "Cancelled";

		// Base Production tab fields editable only when In Progress or earlier
		const base_editable = ["Draft", "In Progress"].includes(status);
		frm.fields_dict["base_raw_materials"].grid.toggle_enable("actual_qty", base_editable && !is_completed);

		// Packaging editable in Packaging or Base Produced
		const pkg_editable = ["Base Produced", "Packaging"].includes(status);
		frm.fields_dict["packaging_items"].grid.toggle_enable("packed_qty", pkg_editable && !is_completed);
		frm.fields_dict["packaging_items"].grid.toggle_enable("container_size_litres", pkg_editable && !is_completed);
	},
});

// ----------------------------------------------------------------
// PM Packaging Item – live recalc
// ----------------------------------------------------------------

frappe.ui.form.on("PM Packaging Item", {
	packed_qty(frm, cdt, cdn) {
		_update_base_used(frm, cdt, cdn);
	},
	container_size_litres(frm, cdt, cdn) {
		_update_base_used(frm, cdt, cdn);
	},
});

function _update_base_used(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	const used = flt(row.container_size_litres) * flt(row.packed_qty);
	frappe.model.set_value(cdt, cdn, "base_qty_used", used);
	frm.trigger("recalculate_remaining");
}

// ----------------------------------------------------------------
// PM Base Material – source warehouse default
// ----------------------------------------------------------------

frappe.ui.form.on("PM Base Material", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.source_warehouse && frm.doc.source_warehouse) {
			frappe.model.set_value(cdt, cdn, "source_warehouse", frm.doc.source_warehouse);
		}
	},
});

// ----------------------------------------------------------------
// PM Quality Reading – auto status
// ----------------------------------------------------------------

frappe.ui.form.on("PM Quality Reading", {
	reading_value(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const val = parseFloat(row.reading_value);
		if (isNaN(val)) return;
		const ok =
			(row.min_value === 0 && row.max_value === 0) ||
			(val >= flt(row.min_value) && val <= flt(row.max_value));
		frappe.model.set_value(cdt, cdn, "status", ok ? "Accepted" : "Rejected");
	},
});
