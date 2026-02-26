import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  ReactFlow, MiniMap, Controls, Background,
  useNodesState, useEdgesState, addEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Bot, Package, TrendingUp, Users, DollarSign, BarChart3,
  Activity, Clock, CheckCircle, RefreshCw, Zap, PlayCircle,
} from 'lucide-react';
import { agentApi } from '@/api/agents';
import { inventoryApi } from '@/api/inventory';
import useChatStore from '@/store/useChatStore';
import toast from 'react-hot-toast';

const initialNodes = [
  {
    id: '1', type: 'default', data: { label: '🤖 Master Agent' }, position: { x: 250, y: 20 },
    style: { background: 'hsl(var(--primary))', color: 'white', border: '2px solid hsl(var(--primary))', borderRadius: '12px', padding: '10px' }
  },
  {
    id: '2', type: 'default', data: { label: '📦 Inventory Agent' }, position: { x: 50, y: 130 },
    style: { background: 'hsl(142 76% 36%)', color: 'white', border: '2px solid hsl(142 76% 36%)', borderRadius: '12px', padding: '10px' }
  },
  {
    id: '3', type: 'default', data: { label: '📊 Forecast Agent' }, position: { x: 200, y: 230 },
    style: { background: 'hsl(221 83% 53%)', color: 'white', border: '2px solid hsl(221 83% 53%)', borderRadius: '12px', padding: '10px' }
  },
  {
    id: '4', type: 'default', data: { label: '🤝 Supplier Agent' }, position: { x: 420, y: 130 },
    style: { background: 'hsl(262 83% 58%)', color: 'white', border: '2px solid hsl(262 83% 58%)', borderRadius: '12px', padding: '10px' }
  },
  {
    id: '5', type: 'default', data: { label: '💰 Pricing Agent' }, position: { x: 370, y: 240 },
    style: { background: 'hsl(25 95% 53%)', color: 'white', border: '2px solid hsl(25 95% 53%)', borderRadius: '12px', padding: '10px' }
  },
  {
    id: '6', type: 'default', data: { label: '🔔 Proactive Agent' }, position: { x: 120, y: 330 },
    style: { background: 'hsl(0 84% 60%)', color: 'white', border: '2px solid hsl(0 84% 60%)', borderRadius: '12px', padding: '10px' }
  },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e1-4', source: '1', target: '4', animated: true },
  { id: 'e2-3', source: '2', target: '3', animated: true },
  { id: 'e2-6', source: '2', target: '6', animated: true },
  { id: 'e4-5', source: '4', target: '5', animated: true },
];

const Agents = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const onConnect = useCallback((params) => setEdges((eds) => addEdge(params, eds)), [setEdges]);

  const { sendMessageToAgent, setChatPanelOpen } = useChatStore();

  const [alerts, setAlerts] = useState([]);
  const [invStatus, setInvStatus] = useState(null);
  const [backendHealthy, setBackendHealthy] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [runningAgent, setRunningAgent] = useState(null);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [alertRes, invRes] = await Promise.all([
        agentApi.getAlerts('store001', 15),
        inventoryApi.getStatus(),
      ]);
      setAlerts(alertRes.alerts || []);
      setInvStatus(invRes);
      setBackendHealthy(true);
    } catch (err) {
      setBackendHealthy(false);
      console.error('Agents data fetch error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const handleRunAgent = async (agentName, query) => {
    setRunningAgent(agentName);
    try {
      sendMessageToAgent(query);
      setChatPanelOpen(true);
      toast.success(`${agentName} triggered! Check the AI panel.`);
    } finally {
      setTimeout(() => setRunningAgent(null), 2000);
    }
  };

  const handleRunForecast = async () => {
    setRunningAgent('Forecast Agent');
    try {
      await inventoryApi.runForecast();
      toast.success('Forecast pipeline started in background!');
    } catch {
      toast.error('Failed to start forecast.');
    } finally {
      setTimeout(() => setRunningAgent(null), 3000);
    }
  };

  // Build agent definitions with real data where possible
  const agents = [
    {
      id: 1,
      name: 'Master Agent',
      icon: Bot,
      status: backendHealthy ? 'active' : 'idle',
      lastActive: backendHealthy ? 'Running' : 'Offline',
      description: 'Central orchestrator that routes queries to specialist agents via intent detection.',
      runQuery: 'Give me a full business overview of my store today.',
    },
    {
      id: 2,
      name: 'Inventory Agent',
      icon: Package,
      status: invStatus ? 'active' : 'idle',
      lastActive: invStatus ? `${invStatus.inventory?.length || 0} products tracked` : 'Idle',
      description: 'Monitors stock levels, detects low-stock conditions, suggests reorder quantities.',
      runQuery: 'Which items in my inventory need immediate restocking?',
    },
    {
      id: 3,
      name: 'Forecast Agent',
      icon: TrendingUp,
      status: 'active',
      lastActive: 'Background pipeline',
      description: 'Predicts demand using sales history, Google Trends, and festival calendar data.',
      runForecast: true,
    },
    {
      id: 4,
      name: 'Supplier Agent',
      icon: Users,
      status: 'active',
      lastActive: 'On demand',
      description: 'Finds and ranks best suppliers for any product, negotiates price and quantity.',
      runQuery: 'Find me the best suppliers for my top low-stock items.',
    },
    {
      id: 5,
      name: 'Pricing Agent',
      icon: DollarSign,
      status: 'active',
      lastActive: 'On demand',
      description: 'Recommends optimal price per product based on demand, competition, and margins.',
      runQuery: 'Give me pricing recommendations for my top 5 products.',
    },
    {
      id: 6,
      name: 'Proactive Agent',
      icon: BarChart3,
      status: alerts.length > 0 ? 'active' : 'idle',
      lastActive: alerts.length > 0 ? `${alerts.length} active alerts` : 'No alerts',
      description: 'Monitors store 24/7 and raises intelligent alerts for anomalies and opportunities.',
      runQuery: 'What proactive actions should I take today to improve my store?',
    },
  ];

  // Activity log from real alerts
  const activityLogs = alerts.slice(0, 8).map((a, i) => ({
    id: i,
    agent: a.type?.includes('stock') ? 'Inventory Agent' : a.type?.includes('price') ? 'Pricing Agent' : 'Proactive Agent',
    action: a.message || a.description || 'Alert generated',
    timestamp: a.created_at ? new Date(a.created_at).toLocaleString('en-IN', { hour: '2-digit', minute: '2-digit' }) : 'Recent',
    status: a.severity === 'critical' ? 'error' : 'success',
  }));

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">AI Agents</h1>
          <p className="text-muted-foreground">Monitor and interact with your live AI agent network</p>
        </div>
        <Button variant="outline" onClick={fetchData} className="gap-2">
          <RefreshCw className="h-4 w-4" />Refresh
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Bot className="h-4 w-4" />Total Agents
            </CardTitle>
          </CardHeader>
          <CardContent><div className="text-2xl font-bold">6</div></CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-600" />Active
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {isLoading ? '—' : agents.filter(a => a.status === 'active').length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground flex items-center gap-2">
              <CheckCircle className="h-4 w-4" />Active Alerts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${alerts.length > 0 ? 'text-amber-600' : 'text-green-600'}`}>
              {isLoading ? '—' : alerts.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium text-muted-foreground">Backend Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${backendHealthy === null ? 'text-muted-foreground' : backendHealthy ? 'text-green-600' : 'text-red-600'}`}>
              {backendHealthy === null ? 'Checking...' : backendHealthy ? 'Online ✓' : 'Offline ✗'}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent Flow Network */}
      <Card>
        <CardHeader>
          <CardTitle>Agent Network</CardTitle>
          <CardDescription>Visual map of how your AI agents connect and collaborate</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ height: '380px' }}>
            <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange} onConnect={onConnect} fitView>
              <Controls />
              <MiniMap />
              <Background variant="dots" gap={12} size={1} />
            </ReactFlow>
          </div>
        </CardContent>
      </Card>

      {/* Agent Cards + Activity Log */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Agent Cards */}
        <Card>
          <CardHeader>
            <CardTitle>Agent Status</CardTitle>
            <CardDescription>Click "Run" to trigger an agent via AI Assistant</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {agents.map((agent, index) => {
                const Icon = agent.icon;
                return (
                  <motion.div key={agent.id}
                    initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.07 }}
                    className="flex items-center gap-4 p-3 rounded-lg border hover:bg-accent transition-colors"
                  >
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${agent.status === 'active' ? 'bg-green-100 dark:bg-green-900' : 'bg-muted'
                      }`}>
                      <Icon className={`h-5 w-5 ${agent.status === 'active' ? 'text-green-600' : 'text-muted-foreground'}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <h4 className="font-semibold text-sm">{agent.name}</h4>
                        <Badge variant={agent.status === 'active' ? 'default' : 'secondary'} className="text-xs">
                          {agent.status}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-1">{agent.description}</p>
                      <div className="flex items-center gap-1 mt-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />{agent.lastActive}
                      </div>
                    </div>
                    <Button size="sm" variant="outline" className="gap-1 shrink-0 text-xs"
                      disabled={runningAgent === agent.name}
                      onClick={() => agent.runForecast ? handleRunForecast() : handleRunAgent(agent.name, agent.runQuery)}>
                      {runningAgent === agent.name ? <RefreshCw className="h-3 w-3 animate-spin" /> : <PlayCircle className="h-3 w-3" />}
                      Run
                    </Button>
                  </motion.div>
                );
              })}
            </div>
          </CardContent>
        </Card>

        {/* Activity Log — from real alerts */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle>Activity Timeline</CardTitle>
                <CardDescription>Recent events from your AI agents</CardDescription>
              </div>
              <Button variant="outline" size="sm" onClick={() => { sendMessageToAgent('Give me a summary of all recent AI agent activity and alerts.'); setChatPanelOpen(true); }}>
                <Zap className="h-4 w-4 mr-1" />Full Analysis
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">{Array(5).fill(0).map((_, i) => <div key={i} className="h-14 rounded-lg bg-muted animate-pulse" />)}</div>
            ) : activityLogs.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <CheckCircle className="h-10 w-10 mx-auto mb-2 text-green-500" />
                <p>No recent agent activity. All systems quiet.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {activityLogs.map((log, index) => (
                  <motion.div key={log.id}
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.07 }}
                    className="flex gap-3 pb-3 border-b last:border-b-0"
                  >
                    <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${log.status === 'error' ? 'bg-red-500' : 'bg-green-500'}`} />
                    <div className="flex-1">
                      <p className="font-medium text-sm">{log.agent}</p>
                      <p className="text-sm text-muted-foreground mt-0.5 line-clamp-2">{log.action}</p>
                      <p className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                        <Clock className="h-3 w-3" />{log.timestamp}
                      </p>
                    </div>
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

export default Agents;
