const express = require('express');
const router = express.Router();
const admin = require('firebase-admin');

const db = admin.firestore();

// 1. READ: Get all inventory items
router.get('/', async (req, res) => {
    try {
        const snapshot = await db.collection('inventory').get();
        const items = snapshot.docs.map(doc => ({
            id: doc.id,
            ...doc.data()
        }));
        res.status(200).json(items);
    } catch (error) {
        console.error("Error fetching inventory:", error);
        res.status(500).json({ error: "Failed to fetch inventory" });
    }
});

// 2. CREATE: Add a new product to inventory
router.post('/', async (req, res) => {
    try {
        const { productName, price, stock, vendorId } = req.body;
        
        // Basic validation
        if (!productName || price === undefined || stock === undefined || !vendorId) {
            return res.status(400).json({ error: "Missing required fields" });
        }

        const newProduct = {
            productName,
            price: Number(price),
            stock: Number(stock),
            vendorId
        };

        const docRef = await db.collection('inventory').add(newProduct);
        res.status(201).json({ id: docRef.id, ...newProduct });
    } catch (error) {
        console.error("Error creating product:", error);
        res.status(500).json({ error: "Failed to add product" });
    }
});

// 3. UPDATE: Update an existing product (e.g., changing stock or price)
router.put('/:id', async (req, res) => {
    try {
        const { id } = req.params;
        const updates = req.body;

        await db.collection('inventory').doc(id).update(updates);
        res.status(200).json({ id, message: "Product updated successfully", updates });
    } catch (error) {
        console.error("Error updating product:", error);
        res.status(500).json({ error: "Failed to update product" });
    }
});

// 4. DELETE: Remove a product from inventory
router.delete('/:id', async (req, res) => {
    try {
        const { id } = req.params;
        await db.collection('inventory').doc(id).delete();
        res.status(200).json({ id, message: "Product deleted successfully" });
    } catch (error) {
        console.error("Error deleting product:", error);
        res.status(500).json({ error: "Failed to delete product" });
    }
});

module.exports = router;