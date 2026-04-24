import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
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
  Sparkles,
  TrendingUp,
  TrendingDown,
  Plus,
  Trash2,
  CheckCircle,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { getPricing, addPricing, deletePricing } from '../../api/pricing';
import { inventoryApi } from '@/api/inventory';
import apiClient from '@/api/client';

const PricingManagement = () => {
  const [pricingRules, setPricingRules] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  // Product name lookup: productId -> product_name
  const [productNameMap, setProductNameMap] = useState({});

  // Apply Price confirmation dialog state
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [applyingRule, setApplyingRule] = useState(null);
  const [isApplying, setIsApplying] = useState(false);

  const [newRule, setNewRule] = useState({ productId: '', basePrice: '', recommendedPrice: '' });

  // Fetch product names from the FastAPI inventory on mount
  useEffect(() => {
    const fetchProductNames = async () => {
      try {
        const data = await inventoryApi.getList();
        const map = {};
        for (const p of data.products || []) {
          const pid = p.product_id || p.id;
          const name = p.product_name || p.productName || p.name;
          if (pid && name) map[pid] = name;
        }
        setProductNameMap(map);
      } catch {
        // Fallback: names won't resolve but page still works
      }
    };
    fetchProductNames();
  }, []);

  useEffect(() => {
    fetchPricing();
  }, []);

  const fetchPricing = async () => {
    setIsLoading(true);
    try {
      const data = await getPricing();
      setPricingRules(data);
    } catch (error) {
      toast.error('Failed to load pricing data');
    } finally {
      setIsLoading(false);
    }
  };

  const getProductName = (productId) => {
    return productNameMap[productId] || productId;
  };

  const handleAddRule = async () => {
    if (!newRule.productId || !newRule.basePrice || !newRule.recommendedPrice) {
      toast.error('Fill all fields'); return;
    }
    try {
      await addPricing(newRule);
      toast.success('Pricing rule added');
      setIsDialogOpen(false);
      setNewRule({ productId: '', basePrice: '', recommendedPrice: '' });
      fetchPricing();
    } catch (error) {
      toast.error('Error adding rule');
    }
  };

  const handleDelete = async (id) => {
    try {
      await deletePricing(id);
      setPricingRules(pricingRules.filter(p => p.id !== id));
      toast.success('Rule deleted');
    } catch (error) {
      toast.error('Error deleting rule');
    }
  };

  // Open the Apply Price confirmation dialog
  const handleApplyClick = (rule) => {
    setApplyingRule(rule);
    setApplyDialogOpen(true);
  };

  // Actually apply the price change
  const handleConfirmApply = async () => {
    if (!applyingRule) return;
    setIsApplying(true);
    try {
      // Update price in PostgreSQL inventory via FastAPI
      await apiClient.patch(`/agent/inventory/update-price/${applyingRule.productId}`, {
        price: Number(applyingRule.recommendedPrice),
      });

      toast.success(
        `Price for "${getProductName(applyingRule.productId)}" updated to ₹${applyingRule.recommendedPrice}`,
        { duration: 4000 }
      );
      setApplyDialogOpen(false);
      setApplyingRule(null);
    } catch (error) {
      console.error('Apply price error:', error);
      toast.error('Failed to apply price. Make sure the product exists in inventory.');
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2"><Sparkles className="h-6 w-6 text-indigo-500" /> AI Pricing Intelligence</h1>
          <p className="text-muted-foreground">Dynamic pricing and margin optimization</p>
        </div>
        
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild><Button><Plus className="h-4 w-4 mr-2" /> Custom Rule</Button></DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Pricing Rule</DialogTitle>
              <DialogDescription>Set a custom pricing rule for a product</DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>Product ID</Label>
                <Input
                  value={newRule.productId}
                  onChange={(e) => setNewRule({...newRule, productId: e.target.value})}
                  placeholder="e.g. prod_003"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Base Price (₹)</Label>
                  <Input
                    type="number"
                    value={newRule.basePrice}
                    onChange={(e) => setNewRule({...newRule, basePrice: e.target.value})}
                    placeholder="0"
                  />
                </div>
                <div className="space-y-2">
                  <Label>AI Recommended (₹)</Label>
                  <Input
                    type="number"
                    value={newRule.recommendedPrice}
                    onChange={(e) => setNewRule({...newRule, recommendedPrice: e.target.value})}
                    placeholder="0"
                  />
                </div>
              </div>
              <Button className="w-full" onClick={handleAddRule}>Save Rule</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <Card>
        <CardHeader><CardTitle>Active Pricing Models</CardTitle></CardHeader>
        <CardContent>
          {isLoading ? <p className="text-muted-foreground">Loading AI recommendations...</p> : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Base Price</TableHead>
                  <TableHead>Recommended</TableHead>
                  <TableHead>Margin Impact</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pricingRules.map((rule, i) => {
                  const diff = rule.recommendedPrice - rule.basePrice;
                  const isPositive = diff >= 0;
                  const name = getProductName(rule.productId);
                  return (
                    <motion.tr key={rule.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.1 }}>
                      <TableCell>
                        <div>
                          <div className="font-medium">{name}</div>
                          {name !== rule.productId && (
                            <div className="text-xs text-muted-foreground font-mono">{rule.productId}</div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>₹{rule.basePrice}</TableCell>
                      <TableCell className="font-bold text-indigo-400">₹{rule.recommendedPrice}</TableCell>
                      <TableCell>
                        <Badge variant={isPositive ? 'default' : 'destructive'} className="flex w-fit gap-1">
                          {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                          {isPositive ? '+' : ''}₹{diff.toFixed(2)}
                        </Badge>
                      </TableCell>
                      <TableCell className="flex gap-2">
                        <Button size="sm" variant="secondary" onClick={() => handleApplyClick(rule)}>
                          <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
                          Apply Price
                        </Button>
                        <Button size="icon" variant="ghost" className="text-red-500" onClick={() => handleDelete(rule.id)}><Trash2 className="h-4 w-4" /></Button>
                      </TableCell>
                    </motion.tr>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Apply Price Confirmation Dialog */}
      <Dialog open={applyDialogOpen} onOpenChange={setApplyDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Confirm Price Change
            </DialogTitle>
            <DialogDescription>
              This will update the product price in your inventory.
            </DialogDescription>
          </DialogHeader>
          {applyingRule && (
            <div className="space-y-4 py-2">
              <div className="p-4 rounded-lg bg-muted/50 border space-y-3">
                <div>
                  <div className="text-xs text-muted-foreground">Product</div>
                  <div className="font-semibold text-lg">{getProductName(applyingRule.productId)}</div>
                  {getProductName(applyingRule.productId) !== applyingRule.productId && (
                    <div className="text-xs text-muted-foreground font-mono">{applyingRule.productId}</div>
                  )}
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground">Current Price</div>
                    <div className="text-lg font-mono line-through text-red-400">₹{applyingRule.basePrice}</div>
                  </div>
                  <div className="text-muted-foreground text-xl">→</div>
                  <div>
                    <div className="text-xs text-muted-foreground">New Price</div>
                    <div className="text-lg font-mono font-bold text-green-400">₹{applyingRule.recommendedPrice}</div>
                  </div>
                </div>
                <div>
                  <Badge
                    variant={applyingRule.recommendedPrice >= applyingRule.basePrice ? 'default' : 'destructive'}
                    className="gap-1"
                  >
                    {applyingRule.recommendedPrice >= applyingRule.basePrice
                      ? <TrendingUp className="h-3 w-3" />
                      : <TrendingDown className="h-3 w-3" />
                    }
                    {applyingRule.recommendedPrice >= applyingRule.basePrice ? '+' : ''}
                    ₹{(applyingRule.recommendedPrice - applyingRule.basePrice).toFixed(2)} per unit
                  </Badge>
                </div>
              </div>

              <div className="flex gap-3">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => { setApplyDialogOpen(false); setApplyingRule(null); }}
                  disabled={isApplying}
                >
                  Cancel
                </Button>
                <Button
                  className="flex-1 gap-2"
                  onClick={handleConfirmApply}
                  disabled={isApplying}
                >
                  {isApplying ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Applying...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="h-4 w-4" />
                      Yes, Apply Price
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default PricingManagement;