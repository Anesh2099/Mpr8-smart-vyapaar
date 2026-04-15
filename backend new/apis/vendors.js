const express = require('express');
const router = express.Router();
const admin = require('firebase-admin');

const db = admin.firestore();

// GET all vendors
router.get('/', async (req, res) => {
    try {
        const snapshot = await db.collection('vendors').get();
        const items = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
        res.status(200).json(items);
    } catch (error) {
        res.status(500).json({ error: "Failed to fetch vendors" });
    }
});

// POST new vendor
router.post('/', async (req, res) => {
    try {
        const { name, location, rating } = req.body;
        if (!name || !location) return res.status(400).json({ error: "Missing fields" });

        const newVendor = { name, location, rating: Number(rating) || 0 };
        const docRef = await db.collection('vendors').add(newVendor);
        res.status(201).json({ id: docRef.id, ...newVendor });
    } catch (error) {
        res.status(500).json({ error: "Failed to add vendor" });
    }
});

// PUT update vendor
router.put('/:id', async (req, res) => {
    try {
        await db.collection('vendors').doc(req.params.id).update(req.body);
        res.status(200).json({ message: "Vendor updated successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to update vendor" });
    }
});

// DELETE vendor
router.delete('/:id', async (req, res) => {
    try {
        await db.collection('vendors').doc(req.params.id).delete();
        res.status(200).json({ message: "Vendor deleted successfully" });
    } catch (error) {
        res.status(500).json({ error: "Failed to delete vendor" });
    }
});

module.exports = router;