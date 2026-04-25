import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { MapPin, Star, Building2, Plus, Trash2, Phone, Package, AlertTriangle } from 'lucide-react';
import toast from 'react-hot-toast';

import { getVendors, addVendor, deleteVendor } from '../../api/vendors';

// ─── React Confirmation Modal (via Portal, not window.confirm) ────────────────
function ConfirmModal({ open, title, message, onConfirm, onCancel }) {
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-background border border-border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 z-10">
        <div className="flex items-start gap-3 mb-4">
          <div className="h-10 w-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center shrink-0">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <h3 className="font-bold text-base text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground mt-1">{message}</p>
          </div>
        </div>
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Yes, Delete</Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
// ─────────────────────────────────────────────────────────────────────────────

const VendorDirectory = () => {
  const [vendors, setVendors] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Delete confirmation state
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, id: null, name: '' });

  const [newVendor, setNewVendor] = useState({ name: '', location: '', reliability: '', contact: '', products: '', notes: '', leadTimeDays: '', price_per_unit: '' });

  useEffect(() => {
    fetchVendors();
  }, []);

  const fetchVendors = async () => {
    setIsLoading(true);
    try {
      const data = await getVendors();
      setVendors(data);
    } catch (error) {
      toast.error('Failed to load vendors');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddVendor = async () => {
    if (!newVendor.name || !newVendor.location) {
      toast.error('Name and location are required');
      return;
    }
    try {
      await addVendor(newVendor);
      toast.success('Vendor added successfully');
      setIsDialogOpen(false);
      setNewVendor({ name: '', location: '', reliability: '', contact: '', products: '', notes: '', leadTimeDays: '', price_per_unit: '' });
      fetchVendors();
    } catch (error) {
      toast.error('Failed to add vendor');
    }
  };

  // Step 1: Show confirm modal
  const requestDelete = (id, name) => {
    setDeleteConfirm({ open: true, id, name });
  };

  // Step 2: User confirmed — do the delete
  const confirmDelete = async () => {
    const { id } = deleteConfirm;
    setDeleteConfirm({ open: false, id: null, name: '' });
    try {
      await deleteVendor(id);
      setVendors(vendors.filter(v => v.id !== id));
      toast.success('Vendor deleted');
    } catch (error) {
      toast.error('Failed to delete vendor');
    }
  };

  const cancelDelete = () => {
    setDeleteConfirm({ open: false, id: null, name: '' });
  };

  return (
    <div className="p-6 space-y-6">
      {/* React Confirmation Modal */}
      <ConfirmModal
        open={deleteConfirm.open}
        title={`Delete "${deleteConfirm.name}"?`}
        message="This will permanently remove this vendor from your directory. This action cannot be undone."
        onConfirm={confirmDelete}
        onCancel={cancelDelete}
      />

      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Vendor Directory</h1>
          <p className="text-muted-foreground">Manage your supplier network</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> Add Supplier</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle>Register New Supplier</DialogTitle></DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2"><Label>Vendor Name</Label><Input value={newVendor.name} onChange={(e) => setNewVendor({...newVendor, name: e.target.value})} placeholder="e.g., Dairy Direct" /></div>
              <div className="space-y-2"><Label>Location</Label><Input value={newVendor.location} onChange={(e) => setNewVendor({...newVendor, location: e.target.value})} placeholder="e.g., Mumbai" /></div>
              <div className="space-y-2"><Label>Reliability (1-5)</Label><Input type="number" step="0.1" value={newVendor.reliability} onChange={(e) => setNewVendor({...newVendor, reliability: e.target.value})} /></div>
              <div className="space-y-2"><Label>Contact Number</Label><Input value={newVendor.contact} onChange={(e) => setNewVendor({...newVendor, contact: e.target.value})} placeholder="e.g., +91-9876543210" /></div>
              <div className="space-y-2"><Label>Products (comma separated)</Label><Input value={newVendor.products} onChange={(e) => setNewVendor({...newVendor, products: e.target.value})} placeholder="e.g., milk, curd, butter" /></div>
              <div className="space-y-2"><Label>Lead Time (days)</Label><Input value={newVendor.leadTimeDays} onChange={(e) => setNewVendor({...newVendor, leadTimeDays: e.target.value})} placeholder="e.g., 1-2" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2"><Label>Price per Unit (₹)</Label><Input type="number" value={newVendor.price_per_unit} onChange={(e) => setNewVendor({...newVendor, price_per_unit: e.target.value})} /></div>
              </div>
              <div className="space-y-2"><Label>Notes</Label><Input value={newVendor.notes} onChange={(e) => setNewVendor({...newVendor, notes: e.target.value})} placeholder="e.g., Minimum order: 10 units" /></div>
              <Button className="w-full" onClick={handleAddVendor}>Save Vendor</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading vendors...</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {vendors.map((vendor, i) => (
            <motion.div key={vendor.id} initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.1 }}>
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-lg flex items-center gap-2"><Building2 className="h-5 w-5 text-blue-500"/> {vendor.name}</CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-500 -mt-2 -mr-2"
                      onClick={() => requestDelete(vendor.id, vendor.name)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center gap-2 text-sm text-muted-foreground"><MapPin className="h-4 w-4" /> {vendor.location}</div>
                  <div className="flex items-center gap-2 text-sm font-semibold"><Star className="h-4 w-4 text-yellow-500 fill-yellow-500" /> {vendor.reliability || vendor.rating || 'N/A'}</div>
                  {vendor.contact && (
                    <div className="flex items-center gap-2 text-sm text-green-600"><Phone className="h-4 w-4" /> {vendor.contact}</div>
                  )}
                  {vendor.products && Array.isArray(vendor.products) && vendor.products.length > 0 && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground flex-wrap">
                      <Package className="h-4 w-4 shrink-0" />
                      {vendor.products.map((p, i) => (
                        <span key={i} className="px-2 py-0.5 bg-muted rounded-full text-xs capitalize">{p}</span>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      )}
    </div>
  );
};

export default VendorDirectory;