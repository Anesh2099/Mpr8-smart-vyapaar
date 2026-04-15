import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import {
  Search,
  Plus,
  Edit,
  Trash2,
  Package,
  AlertTriangle,
  TrendingUp,
  MessageSquare,
  DollarSign,
  RotateCcw,
} from 'lucide-react';
import useChatStore from '@/store/useChatStore';
import toast from 'react-hot-toast';
import { inventoryApi } from '@/api/inventory';

const Inventory = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [products, setProducts] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  const [formData, setFormData] = useState({
    productName: '', sku: '', stock: '', reorderLevel: '', supplier: '', price: ''
  });

  const { sendMessageToAgent, setChatPanelOpen } = useChatStore();

  const totalValue = products.reduce((sum, p) => sum + (Number(p.stock || 0) * Number(p.price || 0)), 0);

  useEffect(() => {
    const fetchInventory = async () => {
      try {
        setIsLoading(true);
        const data = await inventoryApi.getStatus();
        // Backend returns {"products": [...]}
        setProducts(data.products || []);
      } catch (error) {
        console.error("Failed to fetch inventory:", error);
        toast.error("Failed to load inventory data");
      } finally {
        setIsLoading(false);
      }
    };
    fetchInventory();
  }, []);

  const handleInputChange = (e, field) => {
    setFormData({ ...formData, [field]: e.target.value });
  };

  const resetForm = () => {
    setFormData({ productName: '', sku: '', stock: '', reorderLevel: '', supplier: '', price: '' });
    setEditingProduct(null);
  };

  const handleAddSubmit = async () => {
    try {
      if (!formData.productName || !formData.sku) return toast.error("Name and SKU are required");
      const payload = { ...formData, stock: Number(formData.stock), reorderLevel: Number(formData.reorderLevel), price: Number(formData.price) };
      await inventoryApi.addProduct(payload);
      toast.success("Product added successfully!");
      setIsAddOpen(false);
      resetForm();
      const updated = await inventoryApi.getStatus();
      setProducts(updated.products || []);
    } catch (e) { toast.error("Error adding product"); }
  };

  const handleEditClick = (product) => {
    setEditingProduct(product);
    setFormData({
      productName: product.productName || product.name || '',
      sku: product.sku || '',
      stock: product.stock || 0,
      reorderLevel: product.reorderLevel || 0,
      supplier: product.supplier || '',
      price: product.price || 0
    });
    setIsEditOpen(true);
  };

  const handleEditSubmit = async () => {
    try {
      const payload = { ...formData, stock: Number(formData.stock), reorderLevel: Number(formData.reorderLevel), price: Number(formData.price) };
      const id = editingProduct.product_id || editingProduct.id;
      await inventoryApi.updateProduct(id, payload);
      toast.success("Product updated!");
      setIsEditOpen(false);
      resetForm();
      const updated = await inventoryApi.getStatus();
      setProducts(updated.products || []);
    } catch (e) { toast.error("Error updating product"); }
  };

  const handleDelete = async (id, productName) => {
    if (!window.confirm(`Delete "${productName || id}" from inventory? This cannot be undone.`)) return;
    try {
      await inventoryApi.deleteProduct(id);
      toast.success('Product deleted.');
      setProducts(products.filter(p => (p.product_id || p.id) !== id));
    } catch (e) { toast.error('Error deleting product'); }
  };

  const handleAskAgent = (product) => {
    const query = `Check the inventory status for ${product.productName || product.name} and tell me if I need to reorder. It currently has ${product.stock} units.`;
    sendMessageToAgent(query);
    setChatPanelOpen(true);
    toast.success('Query sent to AI Assistant!');
  };

  const handleGetPricing = async (product) => {
    sendMessageToAgent(`Give me a pricing recommendation for ${product.productName || product.name}. Consider demand, competition, and my current margin at ₹${product.price}.`);
    setChatPanelOpen(true);
    toast.success('Pricing analysis sent to AI!');
  };

  const handleGetReorder = async (product) => {
    const productId = product.product_id || product.id;
    try {
      const res = await inventoryApi.getReorderQty(productId);
      const qty = res.recommended_quantity || res.reorder_quantity || res.quantity;
      if (qty) {
        toast.success(`Reorder ${qty} units of ${product.productName || product.name}`, { duration: 5000 });
      } else {
        sendMessageToAgent(`What quantity should I reorder for ${product.productName || product.name}? Current stock: ${product.stock}, reorder level: ${product.reorderLevel}.`);
        setChatPanelOpen(true);
      }
    } catch {
      sendMessageToAgent(`Suggest reorder quantity for ${product.productName || product.name}. Stock: ${product.stock}, reorder level: ${product.reorderLevel}.`);
      setChatPanelOpen(true);
    }
  };

  const getStockLevel = (stock, reorderLevel) => {
    if (stock === 0 || stock <= reorderLevel * 0.5) return 'low';
    if (stock <= reorderLevel) return 'medium';
    return 'good';
  };

  const getStockStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'critical': return 'destructive';
      case 'low': return 'warning';
      case 'ok': return 'success';
      default: return 'secondary';
    }
  };

  const filteredProducts = products.filter((product) => {
    const pName = product.productName || product.name || '';
    const pId = product.product_id || product.id || '';
    return pName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pId.toLowerCase().includes(searchQuery.toLowerCase());
  });

  const handleExportCSV = () => {
    const headers = ['Product Name', 'SKU', 'Stock Level', 'Reorder Target', 'Demand Forecast', 'Supplier Name', 'Price (INR)'];
    const csvContent = [
      headers.join(','),
      ...filteredProducts.map(p => [
        p.productName || p.name || 'N/A',
        p.sku || 'N/A',
        p.stock || 0,
        p.reorderLevel || 0,
        p.forecast || 'N/A',
        p.supplier || 'N/A',
        p.price || 0
      ].join(','))
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `inventory_report_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    toast.success("Inventory exported to CSV!");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Inventory Management</h1>
          <p className="text-muted-foreground">Manage your products and stock levels</p>
        </div>

        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="gap-2" onClick={() => { resetForm(); setIsAddOpen(true); }}>
              <Plus className="h-4 w-4" />
              Add Product
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add New Product</DialogTitle>
              <DialogDescription>Enter the details of the new product</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Product Name</Label>
                <Input value={formData.productName} onChange={e => handleInputChange(e, 'productName')} placeholder="Enter product name" />
              </div>
              <div className="space-y-2">
                <Label>SKU</Label>
                <Input value={formData.sku} onChange={e => handleInputChange(e, 'sku')} placeholder="Enter SKU" />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Stock</Label>
                  <Input type="number" value={formData.stock} onChange={e => handleInputChange(e, 'stock')} placeholder="0" />
                </div>
                <div className="space-y-2">
                  <Label>Reorder Level</Label>
                  <Input type="number" value={formData.reorderLevel} onChange={e => handleInputChange(e, 'reorderLevel')} placeholder="0" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Supplier</Label>
                <Input value={formData.supplier} onChange={e => handleInputChange(e, 'supplier')} placeholder="Supplier name" />
              </div>
              <div className="space-y-2">
                <Label>Price</Label>
                <Input type="number" value={formData.price} onChange={e => handleInputChange(e, 'price')} placeholder="₹0" />
              </div>
              <Button className="w-full" onClick={handleAddSubmit}>Add Product</Button>
            </div>
          </DialogContent>
        </Dialog>

        <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Product</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Product Name</Label>
                <Input value={formData.productName} onChange={e => handleInputChange(e, 'productName')} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Stock</Label>
                  <Input type="number" value={formData.stock} onChange={e => handleInputChange(e, 'stock')} />
                </div>
                <div className="space-y-2">
                  <Label>Reorder Level</Label>
                  <Input type="number" value={formData.reorderLevel} onChange={e => handleInputChange(e, 'reorderLevel')} />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Supplier</Label>
                <Input value={formData.supplier} onChange={e => handleInputChange(e, 'supplier')} />
              </div>
              <div className="space-y-2">
                <Label>Price</Label>
                <Input type="number" value={formData.price} onChange={e => handleInputChange(e, 'price')} />
              </div>
              <Button className="w-full" onClick={handleEditSubmit}>Save Changes</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Package className="h-4 w-4" />
              Total Products
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{products.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 text-red-600" />
              Low Stock
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {products.filter((p) => p.stock < p.reorderLevel).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-green-600" />
              High Demand
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {products.filter((p) => p.forecast === 'High demand').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Value
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">₹{totalValue.toLocaleString('en-IN')}</div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filter */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search products by name or SKU..."
                className="pl-10"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <Button variant="outline" onClick={handleExportCSV}>Export CSV</Button>
          </div>
        </CardContent>
      </Card>

      {/* Products Table */}
      <Card>
        <CardHeader>
          <CardTitle>Products</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Stock</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Forecast</TableHead>
                <TableHead>Supplier</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredProducts.map((product, index) => {
                const stockStatus = getStockLevel(product.stock, product.reorderLevel);
                return (
                  <motion.tr
                    key={product.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="group"
                  >
                    <TableCell>
                      <div>
                        <div className="font-medium">{product.productName || product.name || 'Unknown'}</div>
                        <div className="text-xs text-muted-foreground">{product.category || 'General'}</div>
                      </div>
                    </TableCell>
                    <TableCell className="font-mono text-xs">{product.sku}</TableCell>
                    <TableCell>
                      <div className="font-semibold">{product.stock}</div>
                      <div className="text-xs text-muted-foreground">
                        Reorder: {product.reorderLevel}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          stockStatus === 'low'
                            ? 'destructive'
                            : stockStatus === 'medium'
                              ? 'default'
                              : 'secondary'
                        }
                      >
                        {stockStatus === 'low'
                          ? 'Low Stock'
                          : stockStatus === 'medium'
                            ? 'Normal'
                            : 'Good'}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={product.forecast === 'High demand' ? 'default' : 'outline'}
                      >
                        {product.forecast}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm">{product.supplier}</TableCell>
                    <TableCell className="font-semibold">{product.price}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" title="Edit" onClick={() => handleEditClick(product)}>
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-blue-600" title="Ask AI" onClick={() => handleAskAgent(product)}>
                          <MessageSquare className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-green-600" title="Get AI Pricing" onClick={() => handleGetPricing(product)}>
                          <DollarSign className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-amber-600" title="Suggest Reorder Qty" onClick={() => handleGetReorder(product)}>
                          <RotateCcw className="h-4 w-4" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" title="Delete" onClick={() => handleDelete(product.product_id || product.id, product.productName || product.name)}>
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </motion.tr>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
};

export default Inventory;
