// pricing.js — Now correctly points to the FastAPI backend
// Previously this file targeted a dead http://localhost:5001 URL.
// All pricing functionality is now accessed via inventoryApi.getPricing() in inventory.js.
// This file is kept as a re-export stub for backwards compatibility.
import { inventoryApi } from './inventory';

export const getPricingRecommendation = (productId, storeId = 'store001') =>
    inventoryApi.getPricing(productId, storeId);