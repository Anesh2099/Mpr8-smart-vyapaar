const express = require('express');
const router = express.Router();
const admin = require('firebase-admin');

const db = admin.firestore();

// GET all pricing rules
router.get('/', async (req, res) => {
    try {
        const snapshot = await db.collection('pricing').get();
        const items = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        res.status(200).json(items);
    } catch (error) {
        res.status(500).json({ error: "Failed to fetch pricing data" });
    }
});

// POST new pricing rule
router.post('/', async (req, res) => {
    try {
        const { basePrice, productId, recommendedPrice } = req.body;

        const newPricing = { 
            basePrice: Number(basePrice), 
            productId, 
            recommendedPrice: Number(recommendedPrice) 
        };
        const docRef = await db.collection('pricing').add(newPricing);
        res.status(201).json({ id: docRef.id, ...newPricing });
    } catch (error) {
        res.status(500).json({ error: "Failed to add pricing data" });
    }
});

// PUT update pricing
router.put('/:id', async (req, res) => {
    try {
        await db.collection('pricing').doc(req.params.id).update(req.body);
        res.status(200).json({ message: "Pricing updated successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to update pricing" });
    }
});

// DELETE pricing rule
router.delete('/:id', async (req, res) => {
    try {
        await db.collection('pricing').doc(req.params.id).delete();
        res.status(200).json({ message: "Pricing deleted successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to delete pricing" });
    }
});

module.exports = router;