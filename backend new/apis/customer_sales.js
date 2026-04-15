const express = require('express');
const router = express.Router();
const admin = require('firebase-admin');

const db = admin.firestore();

// GET all customer sales
router.get('/', async (req, res) => {
    try {
        const snapshot = await db.collection('customer_sales').orderBy('timestamp', 'desc').get();
        const items = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        res.status(200).json(items);
    } catch (error) {
        res.status(500).json({ error: "Failed to fetch sales" });
    }
});

// POST new sale
router.post('/', async (req, res) => {
    try {
        const { price, productId, productname, quantity } = req.body;

        const newSale = { 
            price: Number(price), 
            productId, 
            productname, 
            quantity: Number(quantity),
            timestamp: admin.firestore.FieldValue.serverTimestamp()
        };
        const docRef = await db.collection('customer_sales').add(newSale);
        res.status(201).json({ id: docRef.id, ...newSale });
    } catch (error) {
        res.status(500).json({ error: "Failed to record sale" });
    }
});

// PUT update sale
router.put('/:id', async (req, res) => {
    try {
        await db.collection('customer_sales').doc(req.params.id).update(req.body);
        res.status(200).json({ message: "Sale record updated" });
    } catch (error) {
        res.status(500).json({ error: "Failed to update sale" });
    }
});

// DELETE sale
router.delete('/:id', async (req, res) => {
    try {
        await db.collection('customer_sales').doc(req.params.id).delete();
        res.status(200).json({ message: "Sale deleted successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to delete sale" });
    }
});

module.exports = router;