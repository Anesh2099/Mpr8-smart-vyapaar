import { motion } from 'framer-motion';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import {
  TrendingUp,
  TrendingDown,
  Package,
  ShoppingCart,
  AlertTriangle,
  CheckCircle,
  Clock,
  DollarSign,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import useChatStore from '@/store/useChatStore';
import { agentApi } from '@/api/agents';
import { inventoryApi } from '@/api/inventory';
import { salesApi } from '@/api/sales';
import { supplierApi } from '@/api/supplier';
import { useState, useEffect } from 'react';

const Dashboard = () => {
  const { shopInfo, sendMessageToAgent, setChatPanelOpen } = useChatStore();
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const data = await agentApi.getAlerts(shopInfo.id);
        const fetchedAlerts = data.alerts || [];
        setAlerts(fetchedAlerts.slice(0, 5)); // show top 5 on dashboard
      } catch (err) {
        console.error("Failed to load alerts", err);
      }
    };
    fetchAlerts();
  }, [shopInfo.id]);

  const [dashboardStats, setDashboardStats] = useState({
    todaysSales: 0,
    totalOrders: 0,
    lowStock: 0,
    activeProducts: 0
  });

  const [salesData, setSalesData] = useState([]);
  const [topProducts, setTopProducts] = useState([]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [invRes, salesRes, ordersRes] = await Promise.all([
          inventoryApi.getStatus(),
          salesApi.getSales(),
          supplierApi.getPurchaseOrders()
        ]);

        const products = invRes.products || [];
        const sales = salesRes.sales || [];
        const orders = ordersRes.orders || ordersRes.purchase_orders || [];

        const lowStockCount = products.filter(p => Number(p.stock) < Number(p.reorder_level)).length;

        const todayStr = new Date().toISOString().split('T')[0];
        const getDbDateStr = (s) => s.sale_date || (s.timestamp ? new Date(s.timestamp).toISOString().split('T')[0] : "");

        const todaysSalesList = sales.filter(s => getDbDateStr(s) === todayStr);
        const todaysRevenue = todaysSalesList.reduce((sum, s) => sum + (parseFloat(s.total) || parseFloat(s.price) * parseFloat(s.quantity) || 0), 0);

        setDashboardStats({
          todaysSales: todaysRevenue,
          totalOrders: orders.length,
          lowStock: lowStockCount,
          activeProducts: products.length
        });

        // Compute past 7 days sales data for chart
        const past7Days = [...Array(7)].map((_, i) => {
          const d = new Date();
          d.setDate(d.getDate() - (6 - i));
          return d.toISOString().split('T')[0];
        });

        let trends = past7Days.map(date => {
          const daySales = sales.filter(s => getDbDateStr(s) === date);
          const dailyTotal = daySales.reduce((sum, s) => sum + (parseFloat(s.total) || parseFloat(s.price) * parseFloat(s.quantity) || 0), 0);
          const [y, m, d] = date.split('-');
          return { name: `${d}/${m}`, sales: dailyTotal }; // "DD/MM"
        });
        setSalesData(trends);

        // Compute top products
        const productMap = {};
        sales.forEach(sale => {
          if (sale.items) {
            sale.items.forEach(item => {
              if (!productMap[item.product_name]) productMap[item.product_name] = { sales: 0, revenue: 0 };
              productMap[item.product_name].sales += (item.quantity || 1);
              productMap[item.product_name].revenue += (parseFloat(item.price) || 0) * (item.quantity || 1);
            });
          }
        });

        const sortedProducts = Object.keys(productMap)
          .map(name => ({
            name,
            sales: productMap[name].sales,
            revenue: `₹${productMap[name].revenue.toLocaleString('en-IN')}`
          }))
          .sort((a, b) => b.sales - a.sales)
          .slice(0, 4);

        setTopProducts(sortedProducts);

      } catch (err) { console.error("Failed to load dashboard data", err); }
    };

    fetchDashboardData();
  }, []);

  const stats = [
    {
      title: "Today's Sales",
      value: `₹${dashboardStats.todaysSales.toLocaleString('en-IN')}`,
      change: 'Live',
      trend: 'up',
      icon: DollarSign,
    },
    {
      title: 'Total Purchase Orders',
      value: dashboardStats.totalOrders,
      change: 'Active',
      trend: 'up',
      icon: ShoppingCart,
    },
    {
      title: 'Low Stock Items',
      value: dashboardStats.lowStock,
      change: 'Action Needed',
      trend: dashboardStats.lowStock > 0 ? 'down' : 'up',
      icon: AlertTriangle,
    },
    {
      title: 'Active Products',
      value: dashboardStats.activeProducts,
      change: 'In Catalog',
      trend: 'up',
      icon: Package,
    },
  ];

  const handleActionClick = (alert) => {
    // Build rich context so AI knows exactly which product we're discussing
    const productName = alert.product_name || alert.title || alert.type;
    const stockInfo = alert.message || '';
    const action = alert.suggested_action || alert.type;
    const msg = alert.type === 'low_stock'
      ? `I need help with a low stock situation in my kirana store. Product: "${productName}". ${stockInfo}. Suggested action: ${action}. Please give me specific steps to reorder this product, suggest a reorder quantity, and recommend where to source it quickly.`
      : alert.type === 'expiry'
        ? `I need help with a near-expiry product. Product: "${productName}". ${stockInfo}. Please suggest a clearance strategy — should I discount it, bundle it, or promote it? Give me a specific action plan.`
        : `Action requested for: ${productName}. Detail: ${stockInfo}. How should I proceed?`;
    sendMessageToAgent(msg);
    setChatPanelOpen(true);
  };

  const handleDismissAlert = async (e, alertId) => {
    e.stopPropagation();
    if (!window.confirm('Dismiss this alert? It will be removed from your notifications.')) return;
    try {
      await agentApi.dismissAlert(alertId);
      setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
      toast.success('Alert dismissed.');
    } catch (err) {
      toast.error('Failed to dismiss alert.');
    }
  };

  const tasks = [
    { id: 1, text: 'Review proactive notifications', completed: false },
    { id: 2, text: 'Reorder low-stock items via AI', completed: false },
    { id: 3, text: 'Check expected deliveries today', completed: true },
    { id: 4, text: 'Confirm Walk-in sales entries', completed: false },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Welcome back, {shopInfo.owner}! 👋</h1>
          <p className="text-muted-foreground">Here's what's happening with your store today</p>
        </div>
        <Badge variant="outline" className="text-sm">
          <Clock className="h-4 w-4 mr-1" />
          Last updated: Just now
        </Badge>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {stat.title}
                  </CardTitle>
                  <Icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{stat.value}</div>
                  <div className="flex items-center gap-1 text-xs mt-1">
                    {stat.trend === 'up' ? (
                      <TrendingUp className="h-3 w-3 text-green-600" />
                    ) : (
                      <TrendingDown className="h-3 w-3 text-red-600" />
                    )}
                    <span className={stat.trend === 'up' ? 'text-green-600' : 'text-red-600'}>
                      {stat.change}
                    </span>
                    <span className="text-muted-foreground">from last week</span>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* AI Recommendations & Tasks */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* AI Recommendations */}
        <Card>
          <CardHeader>
            <CardTitle>AI Recommendations</CardTitle>
            <CardDescription>Smart insights for your business</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 max-h-[300px] overflow-y-auto pr-2">
              {alerts.length === 0 ? (
                <div className="text-sm text-muted-foreground p-4 text-center border rounded-lg bg-accent/10">
                  No active alerts. Your store is running smoothly!
                </div>
              ) : (
                alerts.map((rec, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex gap-3 p-3 rounded-lg border hover:bg-accent transition-colors cursor-pointer"
                    onClick={() => handleActionClick(rec)}
                  >
                    <div className="shrink-0">
                      <Badge
                        variant={
                          rec.priority === 'urgent'
                            ? 'destructive'
                            : rec.priority === 'high'
                              ? 'warning'
                              : 'secondary'
                        }
                      >
                        {rec.priority || rec.severity || 'info'}
                      </Badge>
                    </div>
                    <div className="flex-1">
                      <h4 className="font-semibold text-sm">{rec.title || rec.type}</h4>
                      <p className="text-sm text-muted-foreground line-clamp-2">{rec.message}</p>
                    </div>
                    {rec.alert_id && (
                      <button
                        className="shrink-0 text-muted-foreground hover:text-red-500 transition-colors p-1 rounded"
                        onClick={(e) => handleDismissAlert(e, rec.alert_id)}
                        title="Dismiss"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </motion.div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Tasks */}
        <Card>
          <CardHeader>
            <CardTitle>Today's Tasks</CardTitle>
            <CardDescription>Things to complete</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {tasks.map((task) => (
                <div
                  key={task.id}
                  className="flex items-center gap-3 p-3 rounded-lg border hover:bg-accent transition-colors"
                >
                  <Checkbox defaultChecked={task.completed} />
                  <span className={task.completed ? 'line-through text-muted-foreground' : ''}>
                    {task.text}
                  </span>
                  {task.completed && <CheckCircle className="h-4 w-4 text-green-600 ml-auto" />}
                </div>
              ))}
            </div>
            <Button
              className="w-full mt-4"
              variant="outline"
              onClick={() => {
                sendMessageToAgent("Can you suggest some daily operational tasks I should add to my list?");
                setChatPanelOpen(true);
              }}
            >
              Ask AI for Tasks
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sales Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Sales Trend</CardTitle>
            <CardDescription>Last 7 days performance</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={salesData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="sales" stroke="hsl(var(--primary))" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Top Products */}
        <Card>
          <CardHeader>
            <CardTitle>Top Products</CardTitle>
            <CardDescription>Best sellers this week</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={topProducts}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-15} textAnchor="end" height={80} fontSize={12} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="sales" fill="hsl(var(--primary))" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Dashboard;
