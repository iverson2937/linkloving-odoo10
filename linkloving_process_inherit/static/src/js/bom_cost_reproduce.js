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
        template: "cost_matching_templ",
        events: {
            'input .origin_bom input': 'origin_bom_search_func',
            // 'blur .origin_bom input':'confirm_origin_bom_sel_func',
            'click .origin_bom ul li':'confirm_origin_bom_sel_func',
            'input .target_bom input':'origin_bom_search_func',
            'click .target_bom ul li':'confirm_target_bom_sel_func'
        },

        //确认目标bom的选择 渲染table表
        confirm_target_bom_sel_func:function () {
            var origin_bom_id = $('.target_bom select option:selected').attr('data-bom-id');
            var target_bom_id = $('.target_bom select option:selected').attr('data-bom-id');
            new Model('mrp.bom').call('get_diff_bom_data',[], {target_bom_id:parseInt(target_bom_id),origin_bom_id:parseInt(origin_bom_id)}).then(function (result) {
                console.log(result);
                $('.cost_matching_container tbody').html('');
                $('.cost_matching_container tbody').append(QWeb.render('cost_matching_tbody_templ',{result:result, target:true}));
            })
        },
        //确认源bom的选择 渲染table表
        confirm_origin_bom_sel_func:function () {
            var bom_id = $('.origin_bom select option:selected').attr('data-bom-id');
            new Model('mrp.bom').call('get_bom_line_list', [[parseInt(bom_id)]]).then(function (result) {
                console.log(result);
                $('.cost_matching_container tbody').html('');
                $('.cost_matching_container tbody').append(QWeb.render('cost_matching_tbody_templ',{result:result, target:false}));
            })
        },
        //源bom、目标bom下的输入框搜索事件
        origin_bom_search_func: _.debounce (function(e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            new Model('mrp.bom').call('get_bom_list', [{name: $(target).parents('td').find('input').val()}]).then(function (result) {
                console.log(result);
                $(target).parents('td').find('select').html('');
                $.when($(target).parents('td').find('select').append(QWeb.render('cost_matching_select_templ',{result:result}))).then(function () {
                     $(target).parents('td').find('select').selectpicker('refresh')
                })
            })
        },300,true),

        init:function (parent, action) {
            this._super(parent);
            this._super.apply(this, arguments);
        },
        start:function () {

        },

    });

    core.action_registry.add('bom_cost_reproduce', BomCostReproduce);

    return BomCostReproduce;


});
