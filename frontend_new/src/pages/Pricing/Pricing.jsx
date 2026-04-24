import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Sparkles,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Info,
} from 'lucide-react';
import toast from 'react-hot-toast';

import { inventoryApi } from '@/api/inventory';
import apiClient from '@/api/client';

const PricingManagement = () => {
  const [recommendations, setRecommendations] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadingProgress, setLoadingProgress] = useState({ done: 0, total: 0 });

  // Apply Price confirmation dialog state
  const [applyDialogOpen, setApplyDialogOpen] = useState(false);
  const [applyingRule, setApplyingRule] = useState(null);
  const [isApplying, setIsApplying] = useState(false);

  useEffect(() => {
    fetchDynamicPricing();
  }, []);

  const fetchDynamicPricing = async () => {
    setIsLoading(true);
    setRecommendations([]);
    try {
      // 1. Get all products from inventory
      const invData = await inventoryApi.getList();
      const products = invData.products || [];

      if (products.length === 0) {
        setIsLoading(false);
        return;
      }

      setLoadingProgress({ done: 0, total: products.length });

      // 2. Get AI pricing recommendation for each product (in parallel batches)
      const batchSize = 2; // Process 2 at a time to stay within Groq rate limits
      const results = [];

      for (let i = 0; i < products.length; i += batchSize) {
        // Small delay between batches to avoid Groq rate limits
        if (i > 0) await new Promise(r => setTimeout(r, 500));
        const batch = products.slice(i, i + batchSize);
        const batchResults = await Promise.allSettled(
          batch.map(async (product) => {
            const pid = product.product_id || product.id;
            try {
              const rec = await inventoryApi.getPricing(pid);
              return {
                ...rec,
                productId: pid,
                productName: rec.productName || product.product_name || product.productName || pid,
              };
            } catch (err) {
              return null;
            }
          })
        );

        for (const r of batchResults) {
          if (r.status === 'fulfilled' && r.value && r.value.recommendedPrice) {
            results.push(r.value);
          }
        }

        setLoadingProgress({ done: Math.min(i + batchSize, products.length), total: products.length });
        // Small partial render update
        setRecommendations([...results]);
      }

      setRecommendations(results);
    } catch (error) {
      console.error('Pricing fetch error:', error);
      toast.error('Failed to load pricing recommendations');
    } finally {
      setIsLoading(false);
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
        `Price for "${applyingRule.productName}" updated to ₹${applyingRule.recommendedPrice}`,
        { duration: 4000 }
      );

      // Update the recommendation in the list to reflect the change
      setRecommendations(prev =>
        prev.map(r =>
          r.productId === applyingRule.productId
            ? { ...r, currentPrice: applyingRule.recommendedPrice, priceChange: '+0.0%' }
            : r
        )
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

  // Stats summary
  const priceIncreases = recommendations.filter(r => r.recommendedPrice > r.currentPrice).length;
  const priceDecreases = recommendations.filter(r => r.recommendedPrice < r.currentPrice).length;
  const avgConfidence = recommendations.length
    ? (recommendations.reduce((s, r) => s + (r.confidence || 0), 0) / recommendations.length * 100).toFixed(0)
    : 0;

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-indigo-500" /> AI Pricing Intelligence
          </h1>
          <p className="text-muted-foreground">
            Dynamic pricing powered by demand, inventory, weather & seasonal signals
          </p>
        </div>

        <Button onClick={fetchDynamicPricing} disabled={isLoading} variant="outline" className="gap-2">
          <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
          {isLoading ? 'Analyzing...' : 'Refresh Prices'}
        </Button>
      </div>

      {/* Stats Row */}
      {recommendations.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <TrendingUp className="h-5 w-5 text-green-500" />
                <div>
                  <div className="text-2xl font-bold">{priceIncreases}</div>
                  <div className="text-sm text-muted-foreground">Price Increases</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <TrendingDown className="h-5 w-5 text-red-500" />
                <div>
                  <div className="text-2xl font-bold">{priceDecreases}</div>
                  <div className="text-sm text-muted-foreground">Price Decreases</div>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <Sparkles className="h-5 w-5 text-indigo-500" />
                <div>
                  <div className="text-2xl font-bold">{avgConfidence}%</div>
                  <div className="text-sm text-muted-foreground">Avg Confidence</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>AI Pricing Recommendations</CardTitle>
          <CardDescription>
            {isLoading
              ? `Analyzing products... (${loadingProgress.done}/${loadingProgress.total})`
              : `${recommendations.length} products analyzed`
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading && recommendations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-3">
              <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
              <p>Running AI pricing analysis on your inventory...</p>
              <p className="text-xs">Evaluating demand, stock levels, weather, and seasonal trends</p>
            </div>
          ) : recommendations.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-muted-foreground gap-3">
              <Info className="h-8 w-8" />
              <p>No products found in inventory. Add products first.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Product</TableHead>
                  <TableHead>Current Price</TableHead>
                  <TableHead>Recommended</TableHead>
                  <TableHead>Change</TableHead>
                  <TableHead>Key Factors</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {recommendations.map((rec, i) => {
                  const diff = rec.recommendedPrice - rec.currentPrice;
                  const isPositive = diff >= 0;
                  const changeStr = rec.priceChange || `${diff >= 0 ? '+' : ''}${((diff / rec.currentPrice) * 100).toFixed(1)}%`;
                  const isNoChange = Math.abs(diff) < 0.01;
                  return (
                    <motion.tr
                      key={rec.productId}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: i * 0.05 }}
                    >
                      <TableCell>
                        <div>
                          <div className="font-medium">{rec.productName}</div>
                          <div className="text-xs text-muted-foreground font-mono">{rec.productId}</div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono">₹{rec.currentPrice}</TableCell>
                      <TableCell className={`font-bold font-mono ${isNoChange ? '' : isPositive ? 'text-green-500' : 'text-red-500'}`}>
                        ₹{rec.recommendedPrice}
                      </TableCell>
                      <TableCell>
                        {isNoChange ? (
                          <Badge variant="outline" className="gap-1 text-muted-foreground">
                            No change
                          </Badge>
                        ) : (
                          <Badge variant={isPositive ? 'default' : 'destructive'} className="flex w-fit gap-1">
                            {isPositive ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
                            {changeStr}
                          </Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[200px]">
                          {rec.factors && rec.factors.length > 0 ? (
                            <p className="text-xs text-muted-foreground line-clamp-2">
                              {rec.factors.slice(0, 2).join('; ')}
                            </p>
                          ) : (
                            <p className="text-xs text-muted-foreground italic">Price is optimal</p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {!isNoChange ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleApplyClick(rec)}
                          >
                            <CheckCircle className="h-3.5 w-3.5 mr-1.5" />
                            Apply
                          </Button>
                        ) : (
                          <Badge variant="outline" className="text-green-600 gap-1">
                            <CheckCircle className="h-3 w-3" />
                            Optimal
                          </Badge>
                        )}
                      </TableCell>
                    </motion.tr>
                  );
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
                  <div className="font-semibold text-lg">{applyingRule.productName}</div>
                  <div className="text-xs text-muted-foreground font-mono">{applyingRule.productId}</div>
                </div>
                <div className="flex items-center gap-4">
                  <div>
                    <div className="text-xs text-muted-foreground">Current Price</div>
                    <div className="text-lg font-mono line-through text-red-400">₹{applyingRule.currentPrice}</div>
                  </div>
                  <div className="text-muted-foreground text-xl">→</div>
                  <div>
                    <div className="text-xs text-muted-foreground">New Price</div>
                    <div className="text-lg font-mono font-bold text-green-400">₹{applyingRule.recommendedPrice}</div>
                  </div>
                </div>
                {applyingRule.factors && applyingRule.factors.length > 0 && (
                  <div>
                    <div className="text-xs text-muted-foreground mb-1">AI Reasoning</div>
                    <ul className="text-xs space-y-1">
                      {applyingRule.factors.map((f, i) => (
                        <li key={i} className="flex gap-1.5 items-start">
                          <Sparkles className="h-3 w-3 mt-0.5 text-indigo-400 shrink-0" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
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