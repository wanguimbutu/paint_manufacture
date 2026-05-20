"""
Minimal Stock Entry override for paint production.

The only change: when the in-memory flag ``pm_paint_entry`` is set (by
CustomWorkOrder._pm_make_stock_entry), validate_finished_goods is replaced
with a paint-aware version that allows multiple distinct finished SKUs while
keeping the Stock Entry type and purpose as "Manufacture" throughout.
"""

import frappe
from frappe import _
from erpnext.stock.doctype.stock_entry.stock_entry import FinishedGoodError, StockEntry


class CustomStockEntry(StockEntry):
	def validate_finished_goods(self):
		if not self.flags.get("pm_paint_entry"):
			super().validate_finished_goods()
			return

		# Paint production: multiple distinct finished SKUs are expected.
		# The only constraint we enforce is that at least one finished item exists.
		# WO-match and single-item checks are intentionally omitted — purpose and
		# stock_entry_type remain "Manufacture" at all times.
		finished_items = [d.item_code for d in self.get("items") if d.is_finished_item]
		if not finished_items:
			frappe.throw(
				msg=_("There must be atleast 1 Finished Good in this Stock Entry"),
				title=_("Missing Finished Good"),
				exc=FinishedGoodError,
			)
