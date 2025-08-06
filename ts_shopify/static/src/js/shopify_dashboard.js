/** @odoo-module **/
odoo.define("ts_shopify.shopify_dashboard_template", function (require) {
    var core = require("web.core");
    var Dialog = require("web.Dialog");
    var Widget = require("web.Widget");
    var rpc = require("web.rpc");



//const ShopifyDashboard = AbstractAction.extend({
//    template: 'shopify_dashboard_template',
//
//    async start() {
//        // Get data from your custom controller
//        const result = await rpc.query({
//            route: '/shopify/dashboard/data',
//        });
//
//        // Render dynamic QWeb template with data
//        this.$el.html(QWeb.render('shopify_dashboard_template', {
//            customer_count: result.customer_count,
//            order_count: result.order_count,
//            product_count: result.product_count,
//        }));
//    }
//});
//
//core.action_registry.add('ts_shopify.client_action', ShopifyDashboard);

export default ShopifyDashboard;
