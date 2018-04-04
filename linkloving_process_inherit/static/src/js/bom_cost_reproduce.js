/**
 * Created by allen on 2018/04/04.
 */
odoo.define('linkloving_process_inherit.bom_cost_reproduce', function (require) {
    "use strict";

    var core = require('web.core');
    var Model = require('web.Model');
    var Widget = require('web.Widget');
    var data = require('web.data');
    var ControlPanelMixin = require('web.ControlPanelMixin');
    var pyeval = require('web.pyeval');
    var QWeb = core.qweb;
    var BomCostReproduce = Widget.extend(ControlPanelMixin, {
        template: "CostDetail",


    });

    core.action_registry.add('bom_cost_reproduce', BomCostReproduce);

    return BomCostReproduce;


});