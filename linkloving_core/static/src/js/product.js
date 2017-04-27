odoo.define('linkloving_core.product_detail', function (require) {
    "use strict";

    var core = require('web.core');
    var Model = require('web.Model');
    var Widget = require('web.Widget');

    var QWeb = core.qweb;
    var _t = core._t;


    var KioskConfirm = Widget.extend({
        template: "HomePage",
        events: {
            'click .click_tag_a': 'show_bom_line',
        },

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.product_id = action.product_id;
            var self = this;
        },
        show_bom_line: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            //小三角的变化
            if(target.classList.contains('show_bom_line_process')||target.classList.contains('show_bom_line_service')){
                target = target.parentNode;
            }
            if(target.childNodes.length > 1){
                if(target.childNodes[1].classList.contains("fa-caret-right")){
                    target.childNodes[1].classList.remove("fa-caret-right")
                    target.childNodes[1].classList.add("fa-caret-down")
                }else if(target.childNodes[1].classList.contains("fa-caret-down")){
                    target.childNodes[1].classList.remove("fa-caret-down")
                    target.childNodes[1].classList.add("fa-caret-right")
                }
            }
            if(target.classList.contains('open-sign')){
                if(target.classList.contains("fa-caret-right")){
                    target.classList.remove("fa-caret-right")
                    target.classList.add("fa-caret-down")
                }else if(target.classList.contains("fa-caret-down")){
                    target.classList.remove("fa-caret-down")
                    target.classList.add("fa-caret-right")
                }
                target = target.parentNode;
            }
            if(target.attributes['data-level'] && target.attributes['data-level'].nodeValue=='true'){
                if(target.attributes['data-product-id']){
                     var product_id = target.attributes['data-product-id'].nodeValue;
                        product_id = parseInt(product_id);
                        // console.log(product_id);
                        new Model("product.template")
                            .call("get_detail", [product_id])
                            .then(function (result) {
                                console.log(result);
                                // console.log(self.$("#"+product_id+">.panel-body").html());
                                self.$("#"+product_id+">.panel-body").html(" ");
                                self.$("#"+product_id+">.panel-body").append(QWeb.render('show_bom_line_tr_add', {bom_lines: result.bom_lines,result:result}));
                            });
                 }
            }
        },
        start: function () {
            var self = this;
            return new Model("product.template")
                .call("get_detail", [this.product_id])
                .then(function (result) {
                    console.log(result);
                    self.$el.append(QWeb.render('show_bom_line_tr', {bom_lines: result.bom_lines,result:result}));
                });

        },
    });

    core.action_registry.add('product_detail', KioskConfirm);

    return KioskConfirm;

});
