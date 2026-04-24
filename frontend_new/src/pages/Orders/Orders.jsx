import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  ShoppingCart,
  Truck,
  Users,
  Phone,
  Mail,
  Star,
  MessageSquare,
  Clock,
  Trash2,
  Search,
  Plus,
} from 'lucide-react';
import useChatStore from '@/store/useChatStore';
import toast from 'react-hot-toast';
import { supplierApi } from '@/api/supplier';
import { getOrders } from '@/api/orders';
import { getVendors } from '@/api/vendors';

const Orders = () => {
  const { sendMessageToAgent, setChatPanelOpen } = useChatStore();
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [orderSearchQuery, setOrderSearchQuery] = useState('');

  // New order form states
  const [isOrderOpen, setIsOrderOpen] = useState(false);
  const [newOrderSupplier, setNewOrderSupplier] = useState('');
  const [newOrderItems, setNewOrderItems] = useState('');
  const [newOrderTotal, setNewOrderTotal] = useState('');

  const formatDate = (timestamp) => {
    if (!timestamp) return 'N/A';
    // If it's a firebase timestamp object
    if (timestamp._seconds) {
      return new Date(timestamp._seconds * 1000).toLocaleDateString('en-GB');
    }
    // If it's a standard date string
    if (typeof timestamp === 'string' && timestamp.includes('-')) {
      return timestamp.split('-').reverse().join('/');
    }
    return new Date(timestamp).toLocaleDateString('en-GB');
  };

  const fetchOrders = async () => {
    try {
      // Switched to Mehul's getOrders API
      const poRes = await getOrders();
      setPurchaseOrders(poRes || []);
    } catch { toast.error("Failed to load orders"); }
  };

  // Deliveries data is kept static as it's not fully handled by backend yet
  const deliveries = [
    {
      id: 'DEL-001',
      poId: 'PO-002',
      supplier: 'Dairy Direct',
      scheduled: '2024-01-16 10:00 AM',
      status: 'In Transit',
      tracking: 'TRK123456789',
    },
    {
      id: 'DEL-002',
      poId: 'PO-001',
      supplier: 'ABC Suppliers',
      scheduled: '2024-01-17 2:00 PM',
      status: 'Scheduled',
      tracking: 'TRK987654321',
    },
  ];

  useEffect(() => {
    const fetchData = async () => {
      setIsLoading(true);
      try {
        // Switched to Mehul's Promise.all fetch strategy
        const [poRes, supRes] = await Promise.all([
          getOrders(),
          getVendors()
        ]);
        setPurchaseOrders(poRes || []);
        setSuppliers(supRes || []);
      } catch (err) {
        console.error("Failed to load data", err);
        toast.error("Failed to load backend data.");
      } finally {
        setIsLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleNegotiate = (supplier) => {
    const name = supplier.supplier_name || supplier.supplierName || supplier.name || 'Unknown';
    const productsList = supplier.products || supplier.categories || [];
    const productsStr = Array.isArray(productsList) ? productsList.join(', ') : (productsList || 'various products');
    const query = `I want to negotiate better prices with my supplier: ${name}. They supply ${productsStr}. Can you draft a negotiation strategy?`;
    sendMessageToAgent(query);
    setChatPanelOpen(true);
    toast.success('Negotiation request sent to AI Agent!');
  };

  const handleContact = (supplier) => {
    if (supplier.email) {
      window.location.href = `mailto:${supplier.email}`;
    } else {
      toast.success(`Contacting ${supplier.supplierName || supplier.name} via ${supplier.contact || supplier.phone || 'phone'}`);
    }
  };

  const handleTrack = (delivery) => {
    toast.success(`Opening tracking information for ${delivery.tracking}...`);
  };

  const handleAddOrder = async () => {
    try {
      if (!newOrderSupplier || !newOrderTotal) return toast.error("Supplier and Total are required");
      const orderData = {
        supplier: newOrderSupplier,
        items: parseInt(newOrderItems) || 1,
        amount: parseFloat(newOrderTotal),
        status: "Pending",
        date: new Date().toISOString().split('T')[0],
        store_id: "store001"
      };
      await supplierApi.addPurchaseOrder(orderData);
      toast.success("Purchase order created!");
      setIsOrderOpen(false);
      setNewOrderSupplier(''); setNewOrderItems(''); setNewOrderTotal('');
      fetchOrders();
    } catch (e) { toast.error("Failed to create order"); }
  };

  const handleDeleteOrder = async (id) => {
    if (!window.confirm('Delete this purchase order? This cannot be undone.')) return;
    try {
      await supplierApi.deletePurchaseOrder(id);
      toast.success("Order deleted");
      fetchOrders();
    } catch (e) { toast.error("Failed to delete order"); }
  };

  const handleAskAgent = (order) => {
    const query = `Analyze the status and impact of this purchase order from ${order.supplier} for ₹${order.amount || order.total}.`;
    sendMessageToAgent(query);
    setChatPanelOpen(true);
    toast.success('Query sent to AI Assistant!');
  };

  // Dynamic stats
  const activeOrdersCount = purchaseOrders.filter(o => o.status !== "Delivered").length;
  const totalSpent = purchaseOrders.reduce((sum, o) => sum + (parseFloat(o.amount) || parseFloat(o.total) || 0), 0);

  const filteredOrders = purchaseOrders.filter(o => {
    const q = orderSearchQuery.toLowerCase();
    if (!q) return true;
    return (
      (o.id && o.id.toLowerCase().includes(q)) ||
      (o.supplier && o.supplier.toLowerCase().includes(q)) ||
      (o.items && o.items.toLowerCase().includes(q))
    );
  });

  const getStatusColor = (status) => {
    if (!status) return 'default';
    switch (status.toLowerCase()) {
      case 'pending':
        return 'default';
      case 'confirmed':
        return 'secondary';
      case 'delivered':
        return 'outline';
      case 'cancelled':
        return 'destructive';
      case 'in transit':
        return 'default';
      case 'scheduled':
        return 'secondary';
      default:
        return 'default';
    }
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Orders & Suppliers</h1>
        <p className="text-muted-foreground">Manage purchase orders and supplier relationships</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <ShoppingCart className="h-4 w-4" />
              Active Orders
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeOrdersCount}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Users className="h-4 w-4" />
              Suppliers
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{suppliers.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Truck className="h-4 w-4" />
              In Transit
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">2</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Spent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">₹{totalSpent.toLocaleString('en-IN')}</div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="orders" className="space-y-4">
        <TabsList>
          <TabsTrigger value="orders">Purchase Orders</TabsTrigger>
          <TabsTrigger value="suppliers">Suppliers</TabsTrigger>
          <TabsTrigger value="deliveries">Deliveries</TabsTrigger>
        </TabsList>

        {/* Purchase Orders Tab */}
        <TabsContent value="orders" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Purchase Orders</CardTitle>
                <CardDescription>Track and manage your purchase orders</CardDescription>
              </div>
              <Dialog open={isOrderOpen} onOpenChange={setIsOrderOpen}>
                <DialogTrigger asChild>
                  <Button>Create New Order</Button>
                </DialogTrigger>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Create Purchase Order</DialogTitle>
                    <DialogDescription>Draft a new order to a supplier</DialogDescription>
                  </DialogHeader>
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>Supplier Name</Label>
                      <select
                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:cursor-not-allowed disabled:opacity-50"
                        value={newOrderSupplier}
                        onChange={e => setNewOrderSupplier(e.target.value)}
                      >
                        <option value="">Select a supplier...</option>
                        {suppliers.map(s => (
                          <option key={s.id} value={s.supplierName || s.name}>{s.supplierName || s.name}</option>
                        ))}
                      </select>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Number of Items</Label>
                        <Input type="number" value={newOrderItems} onChange={e => setNewOrderItems(e.target.value)} placeholder="1" />
                      </div>
                      <div className="space-y-2">
                        <Label>Total Amount (₹)</Label>
                        <Input type="number" value={newOrderTotal} onChange={e => setNewOrderTotal(e.target.value)} placeholder="5000" />
                      </div>
                    </div>
                    <Button className="w-full" onClick={handleAddOrder}>Submit Order</Button>
                  </div>
                </DialogContent>
              </Dialog>
            </CardHeader>
            <CardContent>
              {/* Search bar */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-10"
                  placeholder="Search by PO ID, supplier, or items..."
                  value={orderSearchQuery}
                  onChange={e => setOrderSearchQuery(e.target.value)}
                />
              </div>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>PO ID</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Date</TableHead>
                    <TableHead>Items</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Total</TableHead>
                    <TableHead>Notes</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredOrders.map((order, index) => (
                    <motion.tr
                      key={order.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <TableCell className="font-mono font-semibold">{order.id}</TableCell>
                      <TableCell>{order.supplier}</TableCell>
                      <TableCell>{formatDate(order.timestamp || order.date)}</TableCell>
                      <TableCell>{order.items} items</TableCell>
                      <TableCell>
                        <Badge variant={getStatusColor(order.status)}>{order.status}</Badge>
                      </TableCell>
                      <TableCell className="font-semibold">{order.amount || order.total}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {order.notes || '-'}
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button size="icon" variant="ghost" className="h-8 w-8 text-blue-600" onClick={() => handleAskAgent({ name: order.supplier, ...order })}>
                            <MessageSquare className="h-4 w-4" />
                          </Button>
                          <Button size="icon" variant="ghost" className="h-8 w-8 text-red-600" onClick={() => handleDeleteOrder(order.id)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </motion.tr>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Suppliers Tab */}
        <TabsContent value="suppliers" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {suppliers.map((supplier, index) => (
              <motion.div
                key={supplier.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.1 }}
              >
                <Card className="hover:shadow-lg transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg">{supplier.supplierName || supplier.name}</CardTitle>
                        <CardDescription>{supplier.products ? supplier.products.join(', ') : supplier.specialty}</CardDescription>
                      </div>
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 fill-yellow-400 text-yellow-400" />
                        <span className="font-semibold">{supplier.reliability || supplier.rating}</span>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Phone className="h-4 w-4" />
                        {supplier.contact || supplier.phone}
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Mail className="h-4 w-4" />
                        {supplier.email || 'N/A'}
                      </div>
                      <div className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="h-4 w-4" />
                        Lead Time: {supplier.leadTimeDays || supplier.leadTime} days
                      </div>
                    </div>
                    <div className="flex items-center justify-between pt-2">
                      <Badge variant="secondary">{supplier.totalOrders} orders</Badge>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={() => handleContact(supplier)}>
                          Contact
                        </Button>
                        <Button
                          size="sm"
                          className="gap-2"
                          onClick={() => handleNegotiate(supplier)}
                        >
                          <MessageSquare className="h-4 w-4" />
                          Negotiate
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            ))}
          </div>
        </TabsContent>

        {/* Deliveries Tab */}
        <TabsContent value="deliveries" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Scheduled Deliveries</CardTitle>
              <CardDescription>Track incoming shipments</CardDescription>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Delivery ID</TableHead>
                    <TableHead>PO ID</TableHead>
                    <TableHead>Supplier</TableHead>
                    <TableHead>Scheduled</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Tracking</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deliveries.map((delivery, index) => (
                    <motion.tr
                      key={delivery.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <TableCell className="font-mono font-semibold">{delivery.id}</TableCell>
                      <TableCell className="font-mono">{delivery.poId}</TableCell>
                      <TableCell>{delivery.supplier}</TableCell>
                      <TableCell>{delivery.scheduled}</TableCell>
                      <TableCell>
                        <Badge variant={getStatusColor(delivery.status)}>
                          {delivery.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="font-mono text-xs">{delivery.tracking}</TableCell>
                      <TableCell>
                        <Button size="sm" variant="outline" onClick={() => handleTrack(delivery)}>
                          Track
                        </Button>
                      </TableCell>
                    </motion.tr>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Orders;
