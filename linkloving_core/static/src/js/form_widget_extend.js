odoo.define('linkloving_core.form_widget_extend', function (require) {
    "use strict";

    var core = require('web.core');
    var Model = require('web.Model');
    var Widget = require('web.Widget');

    var ajax = require('web.ajax');
    var crash_manager = require('web.crash_manager');
    var data = require('web.data');
    var datepicker = require('web.datepicker');
    var dom_utils = require('web.dom_utils');
    var Priority = require('web.Priority');
    var ProgressBar = require('web.ProgressBar');
    var Dialog = require('web.Dialog');
    var common = require('web.form_common');
    var formats = require('web.formats');
    var framework = require('web.framework');
    var pyeval = require('web.pyeval');
    var session = require('web.session');
    var utils = require('web.utils');

    var QWeb = core.qweb;
    var _t = core._t;

    var FieldDates = common.fieldDate;
    var form_widget_registry = core.form_widget_registry;

    var substr_time = form_widget_registry.get('date').include({
        render_value: function() {
            if (this.get("effective_readonly")) {
                //add code 2017/5/9 only show year,month,day
                this.$el.text(formats.format_value(this.get('value'), this, '').substring(0,11));
            } else {
                this.datewidget.set_value(this.get('value'));
            }
            // console.log("opopopop")
        }
    });

    core.action_registry.add('form_widget_extend', substr_time);

    return substr_time
});