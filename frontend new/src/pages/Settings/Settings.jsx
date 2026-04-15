import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Separator } from '@/components/ui/separator';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Store,
  Bell,
  Shield,
  Palette,
  Download,
  Save,
  Bot,
} from 'lucide-react';
import useChatStore from '@/store/useChatStore';
import toast from 'react-hot-toast';

const Settings = () => {
  const { shopInfo, updateShopInfo } = useChatStore();

  const handleSave = () => {
    toast.success('Settings saved successfully!');
  };

  const handleExport = () => {
    toast.success('Data export initiated. You will receive an email shortly.');
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">Manage your shop and AI preferences</p>
      </div>

      <Tabs defaultValue="shop" className="space-y-4">
        <TabsList>
          <TabsTrigger value="shop">Shop Info</TabsTrigger>
          <TabsTrigger value="automation">Automation</TabsTrigger>
          <TabsTrigger value="agents">AI Agents</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
        </TabsList>

        {/* Shop Info Tab */}
        <TabsContent value="shop" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Store className="h-5 w-5" />
                Shop Information
              </CardTitle>
              <CardDescription>Update your shop details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Shop Name</Label>
                  <Input defaultValue={shopInfo.name} />
                </div>
                <div className="space-y-2">
                  <Label>Owner Name</Label>
                  <Input defaultValue={shopInfo.owner} />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Location</Label>
                <Input defaultValue={shopInfo.location} />
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Phone Number</Label>
                  <Input placeholder="+91 98765 43210" />
                </div>
                <div className="space-y-2">
                  <Label>Email</Label>
                  <Input type="email" placeholder="shop@example.com" />
                </div>
              </div>
              
              <div className="space-y-2">
                <Label>Business Type</Label>
                <Select defaultValue="grocery">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="grocery">Grocery Store</SelectItem>
                    <SelectItem value="pharmacy">Pharmacy</SelectItem>
                    <SelectItem value="electronics">Electronics</SelectItem>
                    <SelectItem value="clothing">Clothing</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>GST Number</Label>
                <Input placeholder="22AAAAA0000A1Z5" />
              </div>
              
              <Button onClick={handleSave} className="gap-2">
                <Save className="h-4 w-4" />
                Save Changes
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Automation Tab */}
        <TabsContent value="automation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bell className="h-5 w-5" />
                Automation Settings
              </CardTitle>
              <CardDescription>Configure automatic actions and alerts</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Auto Purchase Orders</Label>
                  <p className="text-sm text-muted-foreground">
                    Automatically create purchase orders for low stock items
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Price Optimization</Label>
                  <p className="text-sm text-muted-foreground">
                    Let AI suggest optimal pricing based on market trends
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Stock Alerts</Label>
                  <p className="text-sm text-muted-foreground">
                    Get notified when products are running low
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Demand Forecasting</Label>
                  <p className="text-sm text-muted-foreground">
                    Enable AI-powered demand predictions
                  </p>
                </div>
                <Switch defaultChecked />
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Supplier Auto-Negotiation</Label>
                  <p className="text-sm text-muted-foreground">
                    Allow AI to negotiate prices with suppliers
                  </p>
                </div>
                <Switch />
              </div>
              
              <Button onClick={handleSave} className="gap-2">
                <Save className="h-4 w-4" />
                Save Automation Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* AI Agents Tab */}
        <TabsContent value="agents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-5 w-5" />
                AI Agent Permissions
              </CardTitle>
              <CardDescription>Control what AI agents can do</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <Checkbox id="inventory-agent" defaultChecked />
                  <div className="space-y-1">
                    <Label htmlFor="inventory-agent" className="text-base cursor-pointer">
                      Inventory Agent
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Monitor stock levels, predict shortages, and suggest reorder quantities
                    </p>
                  </div>
                </div>
                
                <Separator />
                
                <div className="flex items-start gap-3">
                  <Checkbox id="forecast-agent" defaultChecked />
                  <div className="space-y-1">
                    <Label htmlFor="forecast-agent" className="text-base cursor-pointer">
                      Forecast Agent
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Analyze trends and predict future sales and demand patterns
                    </p>
                  </div>
                </div>
                
                <Separator />
                
                <div className="flex items-start gap-3">
                  <Checkbox id="supplier-agent" defaultChecked />
                  <div className="space-y-1">
                    <Label htmlFor="supplier-agent" className="text-base cursor-pointer">
                      Supplier Agent
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Find best deals, negotiate prices, and manage supplier relationships
                    </p>
                  </div>
                </div>
                
                <Separator />
                
                <div className="flex items-start gap-3">
                  <Checkbox id="pricing-agent" />
                  <div className="space-y-1">
                    <Label htmlFor="pricing-agent" className="text-base cursor-pointer">
                      Pricing Agent
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Optimize product pricing based on competition and demand
                    </p>
                  </div>
                </div>
                
                <Separator />
                
                <div className="flex items-start gap-3">
                  <Checkbox id="analytics-agent" defaultChecked />
                  <div className="space-y-1">
                    <Label htmlFor="analytics-agent" className="text-base cursor-pointer">
                      Analytics Agent
                    </Label>
                    <p className="text-sm text-muted-foreground">
                      Generate insights and recommendations from your business data
                    </p>
                  </div>
                </div>
              </div>
              
              <Button onClick={handleSave} className="gap-2">
                <Save className="h-4 w-4" />
                Save Agent Permissions
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Preferences Tab */}
        <TabsContent value="preferences" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Palette className="h-5 w-5" />
                Display Preferences
              </CardTitle>
              <CardDescription>Customize your experience</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Language</Label>
                <Select defaultValue="en">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="en">English</SelectItem>
                    <SelectItem value="hi">Hindi</SelectItem>
                    <SelectItem value="mr">Marathi</SelectItem>
                    <SelectItem value="gu">Gujarati</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>Currency</Label>
                <Select defaultValue="inr">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inr">INR (₹)</SelectItem>
                    <SelectItem value="usd">USD ($)</SelectItem>
                    <SelectItem value="eur">EUR (€)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <div className="space-y-2">
                <Label>Time Zone</Label>
                <Select defaultValue="ist">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="ist">IST (Asia/Kolkata)</SelectItem>
                    <SelectItem value="pst">PST (America/Los_Angeles)</SelectItem>
                    <SelectItem value="utc">UTC</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <Separator />
              
              <div className="flex items-center justify-between">
                <div className="space-y-0.5">
                  <Label>Dark Mode</Label>
                  <p className="text-sm text-muted-foreground">
                    Switch to dark theme
                  </p>
                </div>
                <Switch />
              </div>
              
              <Button onClick={handleSave} className="gap-2">
                <Save className="h-4 w-4" />
                Save Preferences
              </Button>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5" />
                Data Management
              </CardTitle>
              <CardDescription>Export or backup your data</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Export Format</Label>
                <Select defaultValue="csv">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="csv">CSV</SelectItem>
                    <SelectItem value="json">JSON</SelectItem>
                    <SelectItem value="excel">Excel</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              
              <Button onClick={handleExport} className="gap-2 w-full" variant="outline">
                <Download className="h-4 w-4" />
                Export All Data
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default Settings;
