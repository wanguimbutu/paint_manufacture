app_name = "paint_manufacture"
app_title = "Paint Manufacture"
app_publisher = "Soria Systems"
app_description = "Paint Manufacture customisation"
app_email = "hello@soriasystems.co.ke"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "paint_manufacture",
# 		"logo": "/assets/paint_manufacture/logo.png",
# 		"title": "Paint Manufacture",
# 		"route": "/paint_manufacture",
# 		"has_permission": "paint_manufacture.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/paint_manufacture/css/paint_manufacture.css"
# app_include_js = "/assets/paint_manufacture/js/paint_manufacture.js"

# include js, css files in header of web template
# web_include_css = "/assets/paint_manufacture/css/paint_manufacture.css"
# web_include_js = "/assets/paint_manufacture/js/paint_manufacture.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "paint_manufacture/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "paint_manufacture/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "paint_manufacture.utils.jinja_methods",
# 	"filters": "paint_manufacture.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "paint_manufacture.install.before_install"
# after_install = "paint_manufacture.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "paint_manufacture.uninstall.before_uninstall"
# after_uninstall = "paint_manufacture.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "paint_manufacture.utils.before_app_install"
# after_app_install = "paint_manufacture.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "paint_manufacture.utils.before_app_uninstall"
# after_app_uninstall = "paint_manufacture.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "paint_manufacture.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"paint_manufacture.tasks.all"
# 	],
# 	"daily": [
# 		"paint_manufacture.tasks.daily"
# 	],
# 	"hourly": [
# 		"paint_manufacture.tasks.hourly"
# 	],
# 	"weekly": [
# 		"paint_manufacture.tasks.weekly"
# 	],
# 	"monthly": [
# 		"paint_manufacture.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "paint_manufacture.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "paint_manufacture.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "paint_manufacture.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["paint_manufacture.utils.before_request"]
# after_request = ["paint_manufacture.utils.after_request"]

# Job Events
# ----------
# before_job = ["paint_manufacture.utils.before_job"]
# after_job = ["paint_manufacture.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"paint_manufacture.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

