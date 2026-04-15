const express = require('express');
const router = express.Router();
const admin = require('firebase-admin');

const db = admin.firestore();

// GET all orders
router.get('/', async (req, res) => {
    try {
        const snapshot = await db.collection('orders').orderBy('timestamp', 'desc').get();
        const items = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        res.status(200).json(items);
    } catch (error) {
        res.status(500).json({ error: "Failed to fetch orders" });
    }
});

// POST new order
router.post('/', async (req, res) => {
    try {
        const { status, supplier } = req.body;
        
        const newOrder = { 
            status: status || 'PENDING', 
            supplier,
            timestamp: admin.firestore.FieldValue.serverTimestamp() // Auto-generates current time
        };
        const docRef = await db.collection('orders').add(newOrder);
        res.status(201).json({ id: docRef.id, ...newOrder });
    } catch (error) {
        res.status(500).json({ error: "Failed to create order" });
    }
});

// PUT update order status
router.put('/:id', async (req, res) => {
    try {
        await db.collection('orders').doc(req.params.id).update(req.body);
        res.status(200).json({ message: "Order updated successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to update order" });
    }
});

// DELETE order
router.delete('/:id', async (req, res) => {
    try {
        await db.collection('orders').doc(req.params.id).delete();
        res.status(200).json({ message: "Order deleted successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to delete order" });
    }
});

module.exports = router;