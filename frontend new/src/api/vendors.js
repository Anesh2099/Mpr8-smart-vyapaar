// vendors.js — Now correctly points to the FastAPI backend
// Previously this file targeted a dead http://localhost:5001 URL.
// All vendor/supplier functionality is now accessed via supplierApi in supplier.js.
// This file is kept as a re-export stub for backwards compatibility.
export { supplierApi as vendorsApi } from './supplier';