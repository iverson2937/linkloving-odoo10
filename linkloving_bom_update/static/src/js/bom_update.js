/**
 * Created by 123 on 2017/5/10.
 */
odoo.define('linkloving_bom_update.bom_update', function (require) {
    "use strict";

    var core = require('web.core');
    var Model = require('web.Model');
    var Widget = require('web.Widget');

    var QWeb = core.qweb;
    var _t = core._t;

    var BomUpdate = Widget.extend({
        template: 'bom_wraper',
        events: {
            'click .click_bom_tag_a': 'show_bom_lists',
            'click .add_product': 'add_product_function',
            'blur .add_product_input': 'add_product_input_blur',
            'focus .add_product_input': 'add_product_input_focus',
            'click .add_product_lis': 'chose_li_to_input',
            'click .bom_modify_submit': 'bom_modify_submit',
            'input .add_product_input': 'when_input_is_on',
            'dblclick .product_name': 'modify_product_fn',
            'click .delete_product': 'delete_product_fn'
        },
        delete_product_fn:function (e) {
            var e = e||window.event;
            var target = e.target || e.srcElement;
            var $target = $(target);
            $target.parents(".panel-default")[0].remove();
            console.log('delete');
        },
        modify_product_fn:function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            var last_product_name = target.innerText;
            var last_product_id = target.getAttribute("data-product-id");
            var wraper = target.parentNode.parentNode.parentNode;
            var inset_before = target.parentNode.parentNode.nextElementSibling;

            target.parentNode.parentNode.parentNode.classList.add("input-panel");
            target.parentNode.parentNode.parentNode.removeChild(target.parentNode.parentNode);
            var divs = document.createElement("div");
            divs.classList.add("panel-heading");
            divs.innerHTML = '<h4 class="panel-title"><div class="add_product_input_wraper"><input id='+last_product_id+' data-product-id='+last_product_id+' class="add_product_input" type="text"/>' +
                '<ul class="add_product_ul"><li></li><li></li><li></li><li></li><li></li><li></li><li></li><li></li></ul>' +
                '<input class="product_propor" style="margin-left: 15px" type="text"/>'+
                '<span class="fa fa-trash-o delete_product" style="margin-left: 15px"></span>'+
                '</div></h4>';

            wraper.insertBefore(divs,inset_before);
            // console.log(target)
            $("input[data-product-id="+last_product_id+"]").attr("value",last_product_name);

            $(".add_product_ul>li").each(function () {
                $(this).addClass("add_product_lis");
            })

        },
        when_input_is_on: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            var change_lis = target.nextElementSibling.childNodes;
            console.log(change_lis)
            return new Model("product.product")
                .call('name_search', [], {
                    name: target.value,
                    limit: 8,
                })
                .then(function (result) {
                    console.log(result);
                    if(result.length==0){
                        for(var i=0;i<8;i++){
                            change_lis[i].innerText = "";
                            change_lis[i].setAttribute("id", "");
                        }
                    }
                    for (var i = 0; i < 8; i++) {
                        if (i >= result.length) {
                            change_lis[i].innerText = "";
                            change_lis[i].setAttribute("id", "");
                        }else {
                            change_lis[i].innerText = result[i][1];
                            change_lis[i].setAttribute("id", result[i][0]);
                        }
                    }
                })
        },
        bom_modify_submit: function () {
            var back_datas = [];
            var top_bom_id = $("#accordion").attr("data-bom-id");
            $(".add_product_input_wraper").each(function () {
                var arr = [];
                var json_data = {};
                var add_product_value = $(this).children("input:first-child").val();
                var add_product_id = $(this).children("input:first-child").prop("id");
                var add_product_qty = $(this).children("input[class='product_propor']").val();

                if($(this).children("input:first-child").attr("data-product-id")!= undefined){
                    var last_product_id = $(this).children("input:first-child").attr("data-product-id");
                }

                if (add_product_value != "") {
                    getParents($(this));
                    console.log(arr);
                    json_data["product_id"] = add_product_id;
                    json_data["parents"] = arr.join(",");
                    json_data["qty"] = add_product_qty;
                    if(typeof(last_product_id)!= "undefined"){
                        json_data["last_product_id"] = last_product_id;
                    }

                    back_datas.push(json_data);

                    $(this).parent().parent().parent().removeClass("input-panel");
                    $(this).parent().html("<a></a><span class='product_name' data-product-id="+add_product_id+">" + add_product_value + "</span><span style='margin-left: 15px'>"+add_product_qty+"</span>");
                } else {
                    $(this).parent().parent().parent().remove()
                }
                //递归 找父级
                function getParents($obj) {
                    if ($obj.parents(".panel-collapse")) {
                        if ($obj.parents(".panel-collapse").length == 0) {
                            return
                        }
                        arr.push($obj.parents(".panel-collapse").attr("data-return-id"));
                        $obj = $obj.parents(".panel-collapse");
                        getParents($obj);
                    }
                }
            });
            console.log(back_datas);

            // return new Model("bom.line")
            //         .call("bom.line.update", [back_datas])
            //         .then(function (result) {
            //             console.log(result);
            //         })
            var action = {
                name: "BOM",
                type: 'ir.actions.act_window',
                res_model: 'bom.update.wizard',
                view_type: 'form',
                view_mode: 'tree,form',
                context: {'back_datas': back_datas, "bom_id": top_bom_id},
                views: [[false, 'form']],
                // res_id: act_id,
                target: "new"
            };
            this.do_action(action);

        },
        chose_li_to_input: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            target.parentNode.previousElementSibling.value = target.innerHTML;
            target.parentNode.previousElementSibling.setAttribute("id", target.getAttribute("id"));
        },
        add_product_input_focus: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            target.nextElementSibling.style.display = "block"
        },
        add_product_input_blur: function () {
            setTimeout(function () {
                $(".add_product_ul").hide()
            }, 150)
        },
        add_product_function: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            var level_add = target.parentNode.parentNode.nextElementSibling;
            var wraper = level_add.getElementsByTagName("div");
            var wheather_input = wraper[0].getElementsByTagName("div");
            if (wheather_input[0].classList.contains("input-panel")) {
                // return
            }
            var divs = document.createElement("div");
            divs.classList.add("panel");
            divs.classList.add("panel-default");
            divs.classList.add("input-panel");
            divs.innerHTML = "<div class='panel-heading'><h4 class='panel-title'><div class='add_product_input_wraper'><input class='add_product_input' type='text'/>" +
                "<ul class='add_product_ul'><li></li><li></li><li></li><li></li><li></li><li></li><li></li><li></li></ul>" +
                "<input class='product_propor' style='margin-left: 15px' type='text'/> "+
                "<span class='fa fa-trash-o delete_product' style='margin-left: 15px'></span>"+
                "</div></h4></div>";
            wraper[0].prepend(divs);
            $(".add_product_ul>li").each(function () {
                $(this).addClass("add_product_lis")
            })
        },

        show_bom_lists: function (e) {
            var e = e || window.event;
            var target = e.target || e.srcElement;
            if (target.childNodes.length > 1) {
                if (target.childNodes[1].classList.contains("fa-caret-right")) {
                    target.childNodes[1].classList.remove("fa-caret-right");
                    target.childNodes[1].classList.add("fa-caret-down");
                } else if (target.childNodes[1].classList.contains("fa-caret-down")) {
                    target.childNodes[1].classList.remove("fa-caret-down");
                    target.childNodes[1].classList.add("fa-caret-right");
                }
            }
            if (target.classList.contains('open-sign')) {
                if (target.classList.contains("fa-caret-right")) {
                    target.classList.remove("fa-caret-right");
                    target.classList.add("fa-caret-down");
                } else if (target.classList.contains("fa-caret-down")) {
                    target.classList.remove("fa-caret-down");
                    target.classList.add("fa-caret-right");
                }
                target = target.parentNode;
            }
        },

        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.bom_id = action.bom_id;
            var self = this;
        },
        start: function () {
            var self = this;
            if (this.bom_id) {
                return new Model("mrp.bom")
                    .call("get_bom", [this.bom_id])
                    .then(function (result) {
                        console.log(result);
                        self.$el.append(QWeb.render('bom_tree', {result: result}))
                        console.log(self.$el.attr("data-bom-id", result.bom_id))
                    })
            }
        }


    })

    core.action_registry.add('bom_update', BomUpdate);

    return BomUpdate;
})