odoo.define('ts_shopify.shopify_stock_import', function (require) {
    'use strict';

    const { Dialog } = require('web.Dialog');
    const { useService } = require('web.core');
    const { Component } = require('web.Component');

    class InventoryCheckComponent extends Component {
        setup() {
            super.setup();
            this.dialog = useService('dialog');
        }

        checkInventory(inventoryItemMap) {
            if (!inventoryItemMap || Object.keys(inventoryItemMap).length === 0) {
                this.dialog.add(Dialog, {
                    title: 'No Inventory Items',
                    body: 'No valid inventory items with SKUs found.',
                });
            }
        }
    }

    return InventoryCheckComponent;
});
