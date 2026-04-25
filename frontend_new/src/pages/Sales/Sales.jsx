import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
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
    TrendingUp,
    ShoppingBag,
    IndianRupee,
    MessageSquare,
    Calendar,
    AlertTriangle,
} from 'lucide-react';
import useChatStore from '@/store/useChatStore';
import toast from 'react-hot-toast';
import { salesApi } from '@/api/sales';
import { inventoryApi } from '@/api/inventory';

const Sales = () => {
    const [searchQuery, setSearchQuery] = useState('');
    const { sendMessageToAgent, setChatPanelOpen } = useChatStore();
    const [salesRecords, setSalesRecords] = useState([]);
    const [inventoryItems, setInventoryItems] = useState([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isDialogOpen, setIsDialogOpen] = useState(false);

    // Form state
    const [newSaleCustomer, setNewSaleCustomer] = useState('');
    const [newSaleProduct, setNewSaleProduct] = useState('');
    const [isOtherProduct, setIsOtherProduct] = useState(false);
    const [otherProductName, setOtherProductName] = useState('');
    const [newSaleTotal, setNewSaleTotal] = useState('');
    const [newSaleMethod, setNewSaleMethod] = useState('Cash');

    // Edit sale state
    const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
    const [editingSale, setEditingSale] = useState(null);
    const [editCustomer, setEditCustomer] = useState('');
    const [editTotal, setEditTotal] = useState('');
    const [editMethod, setEditMethod] = useState('Cash');

    // Date filter
    const [dateFilter, setDateFilter] = useState('All');

    // Confirm modal
    const [confirmState, setConfirmState] = useState({ open: false, title: '', message: '', details: null, onConfirm: null });
    const showConfirm = ({ title, message, details }) =>
        new Promise((resolve) => {
            setConfirmState({
                open: true, title, message, details,
                onConfirm: () => { setConfirmState(s => ({ ...s, open: false })); resolve(true); },
            });
        });
    const handleConfirmCancel = () => setConfirmState(s => ({ ...s, open: false }));

    const fetchData = async () => {
        setIsLoading(true);
        try {
            const [salesRes, invRes] = await Promise.all([
                salesApi.getSales(),
                inventoryApi.getList()
            ]);
            setSalesRecords(salesRes.sales || []);
            setInventoryItems(invRes.inventory || invRes.products || []);
        } catch (err) {
            console.error("Error fetching data:", err);
            toast.error("Failed to load data.");
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleAskAgent = (sale) => {
        const itemsList = sale.items ? sale.items.map(i => i.name).join(', ') : 'N/A';
        const query = `Analyze this recent sale of ₹${sale.total} to ${sale.customer || 'a customer'}. Products sold: ${itemsList}. How does this affect my demand forecast?`;
        sendMessageToAgent(query);
        setChatPanelOpen(true);
        toast.success('Sales data sent to AI Analyst!');
    };

    const handleOpenEditSale = (sale) => {
        setEditingSale(sale);
        setEditCustomer(sale.customer || '');
        setEditTotal(sale.total || '');
        setEditMethod(sale.paymentMethod || 'Cash');
        setIsEditDialogOpen(true);
    };

    const handleEditSale = async () => {
        if (!editingSale) return;
        try {
            const updated = {
                ...editingSale,
                customer: editCustomer,
                total: parseFloat(editTotal),
                paymentMethod: editMethod,
            };
            await salesApi.updateSale(editingSale.id, updated);
            toast.success('Sale updated!');
            setIsEditDialogOpen(false);
            setEditingSale(null);
            fetchData();
        } catch (err) {
            console.error('Edit sale error', err);
            toast.error('Failed to update sale.');
        }
    };

    const handleAddSale = async () => {
        try {
            if (!newSaleTotal || parseFloat(newSaleTotal) <= 0) {
                return toast.error("Please enter a valid total amount.");
            }
            if (!isOtherProduct && !newSaleProduct) {
                return toast.error("Please select a product from the list.");
            }
            if (isOtherProduct && !otherProductName.trim()) {
                return toast.error("Please specify the 'Other' product name.");
            }

            const productName = isOtherProduct ? otherProductName.trim() : newSaleProduct;

            const yes = await showConfirm({
                title: 'Record this Sale?',
                message: 'This will save the sale transaction to your records.',
                details: {
                    customer: newSaleCustomer || 'Walk-in Customer',
                    product: productName,
                    total: `₹${newSaleTotal}`,
                    payment: newSaleMethod || 'Cash',
                },
            });
            if (!yes) return;

            const itemsArray = [{
                name: productName,
                quantity: 1,
                price: parseFloat(newSaleTotal) || 0
            }];

            const saleData = {
                customer: newSaleCustomer || "Walk-in Customer",
                items: itemsArray,
                total: parseFloat(newSaleTotal),
                paymentMethod: newSaleMethod || "Cash",
                status: "Completed",
                date: new Date().toISOString().split('T')[0],
                store_id: 'store001'
            };

            await salesApi.addSale(saleData);
            toast.success("Sale recorded successfully!");
            setIsDialogOpen(false);

            // Reset form
            setNewSaleCustomer('');
            setNewSaleProduct('');
            setIsOtherProduct(false);
            setOtherProductName('');
            setNewSaleTotal('');
            setNewSaleMethod('Cash');

            fetchData();
        } catch (err) {
            console.error("Error adding sale", err);
            toast.error("Failed to add sale. Check console.");
        }
    };

    const handleDeleteSale = async (id) => {
        const yes = await showConfirm({
            title: 'Delete this Sale?',
            message: 'This sale record will be permanently deleted.',
        });
        if (!yes) return;
        try {
            await salesApi.deleteSale(id);
            toast.success("Sale deleted.");
            fetchData();
        } catch (err) {
            console.error("Error deleting sale", err);
            toast.error("Failed to delete sale.");
        }
    }

    const todayStr = new Date().toISOString().split('T')[0];

    const filteredSales = salesRecords.filter((sale) => {
        const q = searchQuery.toLowerCase();
        const matchesSearch =
            (sale.id && sale.id.toLowerCase().includes(q)) ||
            (sale.customer && sale.customer.toLowerCase().includes(q)) ||
            (sale.items && sale.items.some(item => item.name && item.name.toLowerCase().includes(q)));
        if (!matchesSearch) return false;

        if (dateFilter === 'All') return true;
        const d = sale.date || (sale.timestamp ? new Date(sale.timestamp).toISOString().split('T')[0] : null);
        if (!d) return dateFilter === 'All';
        if (dateFilter === 'Today') return d === todayStr;
        if (dateFilter === 'Week') {
            const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 7);
            return new Date(d) >= cutoff;
        }
        if (dateFilter === 'Month') {
            const cutoff = new Date(); cutoff.setDate(cutoff.getDate() - 30);
            return new Date(d) >= cutoff;
        }
        return true;
    });

    const todaysSales = salesRecords.filter(s => {
        const d = s.date || s.timestamp || "";
        return d.startsWith(todayStr);
    });
    const todaysRevenue = todaysSales.reduce((acc, curr) => acc + (parseFloat(curr.total) || 0), 0);

    const handleExportCSV = () => {
        const headers = ['Receipt ID', 'Date', 'Customer', 'Items Purchased', 'Payment Method', 'Total (INR)'];
        const csvContent = [
            headers.join(','),
            ...filteredSales.map(sale => {
                const itemsStr = sale.items ? sale.items.map(i => `${i.quantity}x ${i.name}`).join(' | ') : 'N/A';
                return [
                    sale.id || 'N/A',
                    sale.date || 'N/A',
                    sale.customer || 'Walk-in',
                    itemsStr,
                    sale.paymentMethod || 'Cash',
                    sale.total || 0
                ].join(',');
            })
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `sales_report_${todayStr}.csv`;
        link.click();
        toast.success("Sales exported to CSV!");
    };

    return (
        <>
            {/* React Confirmation Modal via Portal */}
            {confirmState.open && createPortal(
                <div className="fixed inset-0 z-[9999] flex items-center justify-center">
                    <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleConfirmCancel} />
                    <div className="relative bg-background border border-border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 z-10" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-start gap-3 mb-4">
                            <div className="h-10 w-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0">
                                <AlertTriangle className="h-5 w-5 text-amber-600" />
                            </div>
                            <div>
                                <h3 className="font-bold text-base">{confirmState.title}</h3>
                                <p className="text-sm text-muted-foreground mt-1">{confirmState.message}</p>
                            </div>
                        </div>
                        {confirmState.details && (
                            <div className="bg-muted/50 rounded-lg p-3 mb-4 text-xs text-muted-foreground space-y-1">
                                {Object.entries(confirmState.details).map(([k, v]) => v ? (
                                    <div key={k} className="flex justify-between">
                                        <span className="font-medium capitalize">{k}</span>
                                        <span>{String(v)}</span>
                                    </div>
                                ) : null)}
                            </div>
                        )}
                        <div className="flex gap-2 justify-end">
                            <Button variant="outline" onClick={(e) => { e.preventDefault(); e.stopPropagation(); handleConfirmCancel(); }}>Cancel</Button>
                            <Button variant="destructive" onClick={(e) => { e.preventDefault(); e.stopPropagation(); confirmState.onConfirm(); }}>Confirm</Button>
                        </div>
                    </div>
                </div>,
                document.body
            )}
            <div className="p-6 space-y-6">
                {/* Header */}
                <div className="flex justify-between items-center">
                    <div>
                        <h1 className="text-3xl font-bold">Customer Sales</h1>
                        <p className="text-muted-foreground">Manage POS transactions and customer sales records</p>
                    </div>

                    <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                        <DialogTrigger asChild>
                            <Button className="gap-2">
                                <Plus className="h-4 w-4" />
                                New Sale
                            </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-md">
                            <DialogHeader>
                                <DialogTitle>Record New Sale</DialogTitle>
                                <DialogDescription>Enter the purchase details</DialogDescription>
                            </DialogHeader>
                            <div className="space-y-4 py-4">
                                <div className="space-y-2">
                                    <Label>Customer Name</Label>
                                    <Input
                                        placeholder="Walk-in Customer"
                                        value={newSaleCustomer}
                                        onChange={e => setNewSaleCustomer(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Product</Label>
                                    <select
                                        className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                                        value={isOtherProduct ? 'other' : newSaleProduct}
                                        onChange={e => {
                                            if (e.target.value === 'other') {
                                                setIsOtherProduct(true);
                                                setNewSaleProduct('');
                                            } else {
                                                setIsOtherProduct(false);
                                                setNewSaleProduct(e.target.value);
                                                setOtherProductName('');
                                            }
                                        }}
                                    >
                                        <option value="">Select a product from inventory...</option>
                                        {inventoryItems.map(item => {
                                            const name = item.product_name || item.productName || item.name;
                                            return (
                                                <option key={item.id} value={name}>
                                                    {name}
                                                </option>
                                            );
                                        })}
                                        <option value="other">Other (Not in Inventory)</option>
                                    </select>
                                    {isOtherProduct && (
                                        <Input
                                            placeholder="Enter product name"
                                            value={otherProductName}
                                            onChange={e => setOtherProductName(e.target.value)}
                                            className="mt-2"
                                        />
                                    )}
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Total Amount (₹)</Label>
                                        <Input
                                            type="number"
                                            placeholder="₹0"
                                            value={newSaleTotal}
                                            onChange={e => setNewSaleTotal(e.target.value)}
                                            min="1"
                                        />
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Payment Method</Label>
                                        <select
                                            className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                                            value={newSaleMethod}
                                            onChange={e => setNewSaleMethod(e.target.value)}
                                        >
                                            <option value="Cash">Cash</option>
                                            <option value="Card">Card</option>
                                            <option value="UPI">UPI</option>
                                        </select>
                                    </div>
                                </div>
                                <Button className="w-full" onClick={handleAddSale}>Record Transaction</Button>
                            </div>
                        </DialogContent>
                    </Dialog>
                </div>

                {/* Stats Cards */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <IndianRupee className="h-4 w-4 text-green-600" />
                                Today's Revenue
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-green-600">₹{todaysRevenue.toFixed(2)}</div>
                            <p className="text-xs text-muted-foreground mt-1">Calculated from dynamic records</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <ShoppingBag className="h-4 w-4" />
                                Total Transactions
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold">{todaysSales.length}</div>
                            <p className="text-xs text-muted-foreground mt-1">Today</p>
                        </CardContent>
                    </Card>
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
                                <TrendingUp className="h-4 w-4 text-blue-600" />
                                Overall Transactions
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-bold text-blue-600">{salesRecords.length}</div>
                            <p className="text-xs text-muted-foreground mt-1">All time</p>
                        </CardContent>
                    </Card>
                </div>

                {/* Search and Filter */}
                <Card>
                    <CardContent className="pt-6">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                                <Input
                                    placeholder="Search by receipt ID, customer, or product..."
                                    className="pl-10"
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                />
                            </div>
                            <div className="flex gap-1">
                                {['Today', 'Week', 'Month', 'All'].map(f => (
                                    <Button key={f} size="sm" variant={dateFilter === f ? 'default' : 'outline'}
                                        onClick={() => setDateFilter(f)} className="text-xs">
                                        {f}
                                    </Button>
                                ))}
                            </div>
                            <Button variant="outline" onClick={handleExportCSV} className="shrink-0">Export CSV</Button>
                        </div>
                    </CardContent>
                </Card>

                {/* Sales Table */}
                <Card>
                    <CardHeader>
                        <CardTitle>Recent Transactions</CardTitle>
                        {isLoading && <CardDescription>Loading data...</CardDescription>}
                    </CardHeader>
                    <CardContent>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead>Receipt ID</TableHead>
                                    <TableHead>Date</TableHead>
                                    <TableHead>Customer</TableHead>
                                    <TableHead>Items Purchased</TableHead>
                                    <TableHead>Payment</TableHead>
                                    <TableHead>Total</TableHead>
                                    <TableHead>Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredSales.map((sale, index) => (
                                    <motion.tr
                                        key={sale.id}
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ delay: index * 0.05 }}
                                        className="group"
                                    >
                                        <TableCell className="font-mono text-sm font-semibold">{sale.id}</TableCell>
                                        <TableCell>{sale.date ? (sale.date.includes('-') ? sale.date.split('-').reverse().join('/') : sale.date) : (sale.timestamp ? new Date(sale.timestamp).toLocaleDateString('en-GB') : 'N/A')}</TableCell>
                                        <TableCell>{sale.customer || sale.supplier || 'Walk-in'}</TableCell>
                                        <TableCell>
                                            <div className="space-y-1">
                                                {sale.items ? sale.items.map((item, i) => (
                                                    <div key={i} className="text-sm">
                                                        {item.quantity}x {item.name}
                                                    </div>
                                                )) : (
                                                    <div className="text-sm">
                                                        {sale.quantity}x {sale.product_id}
                                                    </div>
                                                )}
                                            </div>
                                        </TableCell>
                                        <TableCell>
                                            <Badge variant="outline">{sale.paymentMethod || 'Cash'}</Badge>
                                        </TableCell>
                                        <TableCell className="font-bold">₹{sale.total || (sale.quantity * 50) || 0}</TableCell>
                                        <TableCell>
                                            <div className="flex gap-2">
                                                <Button size="icon" variant="ghost" className="h-8 w-8" title="Edit Sale" onClick={() => handleOpenEditSale(sale)}>
                                                    <Edit className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    className="h-8 w-8 text-blue-600"
                                                    onClick={() => handleAskAgent(sale)}
                                                    title="Analyze Impact with AI"
                                                >
                                                    <MessageSquare className="h-4 w-4" />
                                                </Button>
                                                <Button
                                                    size="icon"
                                                    variant="ghost"
                                                    className="h-8 w-8 text-red-600"
                                                    onClick={() => handleDeleteSale(sale.id)}
                                                >
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
            </div>
            {/* Edit Sale Dialog */}
            <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
                <DialogContent className="max-w-md">
                    <DialogHeader>
                        <DialogTitle>Edit Sale</DialogTitle>
                        <DialogDescription>Update the details of receipt {editingSale?.id}</DialogDescription>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Customer Name</Label>
                            <Input value={editCustomer} onChange={e => setEditCustomer(e.target.value)} placeholder="Walk-in Customer" />
                        </div>
                        <div className="space-y-2">
                            <Label>Total Amount (₹)</Label>
                            <Input type="number" value={editTotal} onChange={e => setEditTotal(e.target.value)} placeholder="0.00" />
                        </div>
                        <div className="space-y-2">
                            <Label>Payment Method</Label>
                            <select className="w-full border rounded-md p-2 bg-background text-foreground text-sm" value={editMethod} onChange={e => setEditMethod(e.target.value)}>
                                <option>Cash</option>
                                <option>UPI</option>
                                <option>Card</option>
                                <option>Net Banking</option>
                            </select>
                        </div>
                    </div>
                    <div className="flex gap-2 justify-end">
                        <Button variant="outline" onClick={() => setIsEditDialogOpen(false)}>Cancel</Button>
                        <Button onClick={handleEditSale}>Save Changes</Button>
                    </div>
                </DialogContent>
            </Dialog>
        </>
    );
};

export default Sales;
