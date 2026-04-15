const express = require('express');
const cors = require('cors');
const admin = require('firebase-admin');

// Initialize Firebase Admin
const serviceAccount = require('./serviceAccountKey.json');
if (!admin.apps.length) {
    admin.initializeApp({
        credential: admin.credential.cert(serviceAccount)
    });
}

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Import Routes
const inventoryRoutes = require('./apis/inventory');
const vendorsRoutes = require('./apis/vendors');
const ordersRoutes = require('./apis/orders');
const customerSalesRoutes = require('./apis/customer_sales');
const pricingRoutes = require('./apis/pricing');

// Use Routes
app.use('/api/inventory', inventoryRoutes);
app.use('/api/vendors', vendorsRoutes);
app.use('/api/orders', ordersRoutes);
app.use('/api/customer_sales', customerSalesRoutes);
app.use('/api/pricing', pricingRoutes);

const PORT = process.env.PORT || 5001;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});