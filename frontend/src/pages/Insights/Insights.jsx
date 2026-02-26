import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import {
  TrendingUp, TrendingDown, Sparkles, AlertCircle, CheckCircle,
  Clock, RefreshCw, X, Calendar, Package, Zap,
} from 'lucide-react';
import useChatStore from '@/store/useChatStore';
import { agentApi } from '@/api/agents';
import { salesApi } from '@/api/sales';
import { inventoryApi } from '@/api/inventory';
import toast from 'react-hot-toast';

// ── Skeleton Loader ──────────────────────────────────────────────────────────
const SkeletonCard = () => (
  <div className="h-32 rounded-lg bg-muted animate-pulse" />
);
const SkeletonChart = () => (
  <div className="h-64 rounded-lg bg-muted animate-pulse" />
);

// ── Helpers ──────────────────────────────────────────────────────────────────
const getMonthLabel = (dateStr) => {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' });
};

const Insights = () => {
  const { sendMessageToAgent, setChatPanelOpen } = useChatStore();

  // State
  const [alerts, setAlerts] = useState([]);
  const [salesRecords, setSalesRecords] = useState([]);
  const [inventory, setInventory] = useState([]);
  const [festivals, setFestivals] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isForecastRunning, setIsForecastRunning] = useState(false);

  // Derived chart data from real records
  const salesTrend = (() => {
    if (!salesRecords.length) return [];
    // Group by date (last 7 days)
    const byDate = {};
    salesRecords.slice(0, 100).forEach(s => {
      const d = (s.date || (s.timestamp ? new Date(s.timestamp).toISOString().split('T')[0] : null));
      if (d) {
        byDate[d] = (byDate[d] || 0) + (parseFloat(s.total) || 0);
      }
    });
    return Object.entries(byDate)
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-10)
      .map(([date, sales]) => ({ day: getMonthLabel(date), sales: Math.round(sales) }));
  })();

  const productDemand = (() => {
    if (!inventory.length) return [];
    // Count items by stock used: reorderLevel - stock = implied demand proxy
    return inventory
      .filter(p => p.productName || p.name)
      .slice(0, 8)
      .map(p => ({
        product: (p.productName || p.name || '').slice(0, 10),
        stock: p.stock || 0,
        reorder: p.reorderLevel || 0,
      }));
  })();

  const stockHealth = (() => {
    if (!inventory.length) return [];
    const inStock = inventory.filter(p => (p.stock || 0) > (p.reorderLevel || 0)).length;
    const lowStock = inventory.filter(p => (p.stock || 0) <= (p.reorderLevel || 0) && (p.stock || 0) > 0).length;
    const outOfStock = inventory.filter(p => (p.stock || 0) === 0).length;
    return [
      { name: 'In Stock', value: inStock, fill: '#22c55e' },
      { name: 'Low Stock', value: lowStock, fill: '#f59e0b' },
      { name: 'Out of Stock', value: outOfStock, fill: '#ef4444' },
    ];
  })();

  // Fetch all data
  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [alertRes, salesRes, invRes] = await Promise.all([
        agentApi.getAlerts('store001', 20),
        salesApi.getSales(),
        inventoryApi.getStatus(),
      ]);
      setAlerts(alertRes.alerts || []);
      setSalesRecords(salesRes.sales || []);
      setInventory(invRes.inventory || invRes.products || []);
    } catch (err) {
      console.error('Insights fetch error:', err);
      toast.error('Failed to load insights data.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchFestivals = async () => {
    try {
      const res = await inventoryApi.getFestivals();
      // API returns an array directly e.g. [{festival, advice, date}, ...]
      // Filter out error objects (e.g. {error: 'credentials...'}) — backend now handles this
      const arr = Array.isArray(res) ? res.filter(f => !f.error) : [];
      setFestivals(arr);
    } catch (err) {
      console.warn('Festival data unavailable:', err);
      setFestivals([]);
    }
  };

  useEffect(() => {
    fetchData();
    fetchFestivals();
  }, []);

  const handleRunForecast = async () => {
    setIsForecastRunning(true);
    try {
      await inventoryApi.runForecast();
      toast.success(
        '🚀 Forecast pipeline started! This runs in the background and takes ~2-3 minutes. Results will appear in the Inventory page under each product and in the AI chat when you ask about demand.',
        { duration: 8000 }
      );
      sendMessageToAgent('The demand forecast pipeline has just been triggered. Once it completes, what should I look for in the updated forecast data?');
      setChatPanelOpen(true);
    } catch (err) {
      toast.error('Failed to start forecast pipeline. Is the backend running?');
    } finally {
      setTimeout(() => setIsForecastRunning(false), 4000);
    }
  };

  const handleDismissAlert = async (alertId) => {
    try {
      await agentApi.dismissAlert(alertId);
      setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
      toast.success('Alert dismissed.');
    } catch (err) {
      toast.error('Failed to dismiss alert.');
    }
  };

  const handleChartAI = (chartName) => {
    sendMessageToAgent(`Can you analyze the ${chartName} data and give me detailed insights and recommendations?`);
    setChatPanelOpen(true);
    toast.success('Analysis request sent to AI!');
  };

  const getImpactColor = (impact) => {
    if (impact === 'high') return 'destructive';
    if (impact === 'medium') return 'secondary';
    return 'outline';
  };

  const totalRevenue = salesRecords.reduce((s, r) => s + (parseFloat(r.total) || 0), 0);
  const avgSale = salesRecords.length ? (totalRevenue / salesRecords.length).toFixed(0) : 0;
  const lowStockCount = inventory.filter(p => (p.stock || 0) <= (p.reorderLevel || 0)).length;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Business Insights</h1>
          <p className="text-muted-foreground">AI-powered analytics from your live store data</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchData} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Button size="sm" onClick={handleRunForecast} disabled={isForecastRunning} className="gap-2">
            <Zap className="h-4 w-4" />
            {isForecastRunning ? 'Running...' : 'Run Forecast'}
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {isLoading ? (
          Array(4).fill(0).map((_, i) => <SkeletonCard key={i} />)
        ) : (
          <>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground flex gap-2 items-center"><TrendingUp className="h-4 w-4 text-green-500" />Total Revenue</CardTitle></CardHeader>
                <CardContent><div className="text-2xl font-bold">₹{totalRevenue.toLocaleString('en-IN')}</div><p className="text-xs text-muted-foreground">from {salesRecords.length} sales</p></CardContent>
              </Card>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground flex gap-2 items-center"><Sparkles className="h-4 w-4 text-blue-500" />Avg Sale Value</CardTitle></CardHeader>
                <CardContent><div className="text-2xl font-bold">₹{avgSale}</div><p className="text-xs text-muted-foreground">per transaction</p></CardContent>
              </Card>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground flex gap-2 items-center"><Package className="h-4 w-4 text-amber-500" />Low Stock Items</CardTitle></CardHeader>
                <CardContent><div className={`text-2xl font-bold ${lowStockCount > 0 ? 'text-amber-600' : 'text-green-600'}`}>{lowStockCount}</div><p className="text-xs text-muted-foreground">need reordering</p></CardContent>
              </Card>
            </motion.div>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm text-muted-foreground flex gap-2 items-center"><AlertCircle className="h-4 w-4 text-red-500" />Active Alerts</CardTitle></CardHeader>
                <CardContent><div className={`text-2xl font-bold ${alerts.length > 0 ? 'text-red-600' : 'text-green-600'}`}>{alerts.length}</div><p className="text-xs text-muted-foreground">from AI agents</p></CardContent>
              </Card>
            </motion.div>
          </>
        )}
      </div>

      {/* AI Insights Cards */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-purple-500" />Live AI Insights</CardTitle>
              <CardDescription>Real-time alerts from your AI agents</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">{Array(3).fill(0).map((_, i) => <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />)}</div>
          ) : alerts.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <CheckCircle className="h-10 w-10 mx-auto mb-2 text-green-500" />
              <p>No active alerts. Your store is running smoothly!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {alerts.map((alert, i) => (
                <motion.div
                  key={alert.alert_id || i}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="flex items-start gap-3 p-4 rounded-lg border bg-accent/30 hover:bg-accent/50 transition-colors"
                >
                  <AlertCircle className="h-5 w-5 text-amber-500 mt-0.5 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="font-medium text-sm">{alert.type || 'Alert'}</span>
                      <Badge variant={getImpactColor(alert.severity || alert.impact)}>{alert.severity || alert.impact || 'info'}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{alert.message || alert.description}</p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-blue-500"
                      onClick={() => { sendMessageToAgent(`Tell me more about this alert: ${alert.message || alert.description}`); setChatPanelOpen(true); }}>
                      <Sparkles className="h-3 w-3" />
                    </Button>
                    {alert.alert_id && (
                      <Button size="icon" variant="ghost" className="h-7 w-7 text-muted-foreground hover:text-red-500"
                        onClick={() => handleDismissAlert(alert.alert_id)}>
                        <X className="h-3 w-3" />
                      </Button>
                    )}
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales Trend */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Revenue Trend</CardTitle>
                <CardDescription>Daily revenue from real sales records</CardDescription>
              </div>
              <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => handleChartAI('revenue trend')}>
                <Sparkles className="h-3 w-3" />Analyze
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? <SkeletonChart /> : salesTrend.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground">No sales data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={salesTrend}>
                  <defs>
                    <linearGradient id="salesGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={v => `₹${v}`} />
                  <Tooltip formatter={v => [`₹${v}`, 'Revenue']} />
                  <Area type="monotone" dataKey="sales" stroke="hsl(var(--primary))" fill="url(#salesGrad)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Product Stock Levels */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Product Stock Levels</CardTitle>
                <CardDescription>Current stock vs reorder threshold</CardDescription>
              </div>
              <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => handleChartAI('stock levels')}>
                <Sparkles className="h-3 w-3" />Analyze
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? <SkeletonChart /> : productDemand.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-muted-foreground">No inventory data yet</div>
            ) : (
              <ResponsiveContainer width="100%" height={240}>
                <BarChart data={productDemand} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis type="number" tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="product" tick={{ fontSize: 11 }} width={70} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="stock" name="In Stock" fill="hsl(142 76% 36%)" radius={[0, 4, 4, 0]} />
                  <Bar dataKey="reorder" name="Reorder At" fill="hsl(25 95% 53%)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Inventory Health + Festival Advisor */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Inventory Health */}
        <Card>
          <CardHeader>
            <CardTitle>Inventory Health</CardTitle>
            <CardDescription>Stock status distribution across all products</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? <SkeletonChart /> : (
              <div className="space-y-4 pt-2">
                {stockHealth.map((item) => (
                  <div key={item.name} className="flex items-center gap-3">
                    <div className="w-3 h-3 rounded-full shrink-0" style={{ background: item.fill }} />
                    <div className="flex-1">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">{item.name}</span>
                        <span className="text-muted-foreground">{item.value} products</span>
                      </div>
                      <div className="h-2 rounded-full bg-muted">
                        <div className="h-2 rounded-full transition-all" style={{
                          width: `${inventory.length ? (item.value / inventory.length * 100) : 0}%`,
                          background: item.fill,
                        }} />
                      </div>
                    </div>
                  </div>
                ))}
                <div className="pt-2 text-xs text-muted-foreground">
                  {inventory.length} total products tracked
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Festival Advisor */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Calendar className="h-5 w-5 text-orange-500" />Festival Advisor
                </CardTitle>
                <CardDescription>AI stocking recommendations for upcoming events</CardDescription>
              </div>
              <Button variant="ghost" size="sm" className="gap-1 text-xs" onClick={() => { sendMessageToAgent('What festivals are coming up in the next 15 days and what stock should I prepare?'); setChatPanelOpen(true); }}>
                <Sparkles className="h-3 w-3" />Ask AI
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {festivals === null ? (
              // Loading
              <div className="space-y-3">
                {[0, 1, 2].map(i => <div key={i} className="h-16 rounded-lg bg-muted animate-pulse" />)}
              </div>
            ) : festivals.length === 0 ? (
              <div className="text-sm text-muted-foreground p-4 text-center">
                No upcoming festival data. Click <strong>Ask AI</strong> for seasonal advice.
              </div>
            ) : (
              <div className="space-y-3">
                {festivals.slice(0, 4).map((f, i) => (
                  <motion.div key={i} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.08 }}
                    className="p-3 rounded-lg border bg-orange-50/10 border-orange-200/20">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{f.festival || f.name}</span>
                      {f.date && <Badge variant="outline" className="text-xs">{f.date}</Badge>}
                    </div>
                    <p className="text-xs text-muted-foreground">{f.advice || f.recommendation || f.description}</p>
                  </motion.div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Insights;
