import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronRight,
  Send,
  Mic,
  Sparkles,
  Bot,
  User,
  AlertCircle,
  CheckCircle2,
  AlertTriangle,
  History,
  Trash2,
  Plus,
  Clock,
} from 'lucide-react';
import { createPortal } from 'react-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import useChatStore from '@/store/useChatStore';
import apiClient from '@/api/client';
import { supplierApi } from '@/api/supplier';
import toast from 'react-hot-toast';

// ─── Inline Confirmation Modal (uses React Portal, NOT window.confirm) ─────────
function ConfirmModal({ open, title, message, details, onConfirm, onCancel }) {
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-background border border-border rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 z-10 animate-in fade-in zoom-in-95">
        <div className="flex items-start gap-3 mb-4">
          <div className="h-10 w-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center shrink-0 mt-0.5">
            <AlertTriangle className="h-5 w-5 text-amber-600" />
          </div>
          <div>
            <h3 className="font-bold text-base text-foreground">{title}</h3>
            <p className="text-sm text-muted-foreground mt-1">{message}</p>
          </div>
        </div>
        {details && (
          <div className="bg-muted/50 rounded-lg p-3 mb-4 text-xs text-muted-foreground space-y-1">
            {Object.entries(details).map(([k, v]) => v ? (
              <div key={k} className="flex justify-between">
                <span className="font-medium capitalize">{k.replace(/_/g, ' ')}</span>
                <span>{String(v)}</span>
              </div>
            ) : null)}
          </div>
        )}
        <div className="flex gap-2 justify-end">
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Yes, Confirm</Button>
        </div>
      </div>
    </div>,
    document.body
  );
}
// ─────────────────────────────────────────────────────────────────────────────

const ChatPanel = () => {
  const {
    messages,
    isChatPanelOpen,
    toggleChatPanel,
    addMessage,
    activeAgents,
    isTyping,
    sendMessageToAgent,
    sessions,
    sessionId,
    showHistory,
    toggleHistory,
    startNewSession,
    switchSession,
    deleteSession,
  } = useChatStore();

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef(null);

  // Confirmation modal state
  const [confirmState, setConfirmState] = useState({
    open: false,
    title: '',
    message: '',
    details: null,
    onConfirm: null,
  });

  const showConfirm = ({ title, message, details }) =>
    new Promise((resolve) => {
      setConfirmState({
        open: true,
        title,
        message,
        details,
        onConfirm: () => {
          setConfirmState(s => ({ ...s, open: false }));
          resolve(true);
        },
      });
    });

  const handleConfirmCancel = () => {
    setConfirmState(s => ({ ...s, open: false }));
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const suggestedPrompts = [
    'Forecast next week sales',
    'Find best supplier',
    'Show low stock items',
    'Analyze top products',
  ];

  const handleSendMessage = () => {
    if (!inputValue.trim() || isTyping) return;
    sendMessageToAgent(inputValue);
    setInputValue('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') handleSendMessage();
  };

  return (
    <>
      {/* Confirmation Modal rendered via Portal */}
      <ConfirmModal
        open={confirmState.open}
        title={confirmState.title}
        message={confirmState.message}
        details={confirmState.details}
        onConfirm={confirmState.onConfirm}
        onCancel={handleConfirmCancel}
      />

      <AnimatePresence>
        {isChatPanelOpen && (
          <motion.aside
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: '30%', opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="min-w-[350px] h-screen bg-card border-l-2 border-accent/30 flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="p-4 border-b border-border bg-gradient-to-r from-primary/10 to-accent/10">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="relative">
                    <Bot className="h-6 w-6 text-primary" />
                    <div className="absolute -top-1 -right-1 w-2 h-2 bg-accent rounded-full animate-pulse"></div>
                  </div>
                  <h2 className="font-bold text-lg">Agent Saarthi</h2>
                </div>
                <div className="flex items-center gap-1">
                  <Button variant="ghost" size="icon" onClick={startNewSession} className="h-8 w-8 hover:bg-accent/20" title="New Chat">
                    <Plus className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={toggleHistory} className={`h-8 w-8 hover:bg-accent/20 ${showHistory ? 'bg-accent/30' : ''}`} title="Chat History">
                    <History className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={toggleChatPanel} className="h-8 w-8 hover:bg-accent/20">
                    <ChevronRight className="h-5 w-5" />
                  </Button>
                </div>
              </div>

              {activeAgents.length > 0 && (
                <div className="flex gap-2 flex-wrap mt-2">
                  {activeAgents.map((agent) => (
                    <Badge key={agent} variant="secondary" className="text-xs">
                      <Sparkles className="h-3 w-3 mr-1" />
                      {agent}
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            {/* History Panel */}
            {showHistory && (
              <div className="border-b border-border bg-muted/30 max-h-[280px] overflow-y-auto">
                <div className="p-3">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Chat History</p>
                  <div className="space-y-1">
                    {sessions.map(session => (
                      <div
                        key={session.id}
                        className={`flex items-center gap-2 p-2 rounded-lg cursor-pointer group transition-colors ${session.id === sessionId ? 'bg-primary/10 text-primary' : 'hover:bg-accent/20'}`}
                        onClick={() => switchSession(session.id)}
                      >
                        <Clock className="h-3.5 w-3.5 shrink-0 opacity-60" />
                        <span className="text-xs flex-1 truncate">{session.label}</span>
                        <button
                          onClick={(e) => { e.stopPropagation(); deleteSession(session.id); }}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground hover:text-red-500 transition-all"
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`flex gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : 'bg-secondary'
                      }`}
                  >
                    {message.role === 'user' ? (
                      <User className="h-4 w-4" />
                    ) : (
                      <Bot className="h-4 w-4" />
                    )}
                  </div>
                  <Card
                    className={`p-3 max-w-[85%] ${message.role === 'user'
                      ? 'bg-primary text-primary-foreground'
                      : message.isError
                        ? 'bg-destructive/10 border-destructive flex flex-col gap-2 text-destructive'
                        : 'bg-accent/10 border-accent/30 flex flex-col gap-3'
                      }`}
                  >
                    <div
                      className="text-sm whitespace-pre-wrap leading-relaxed"
                      dangerouslySetInnerHTML={{
                        __html: message.content
                          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                          .replace(/\n/g, '<br/>')
                      }}
                    />

                    {/* Action Cards */}
                    {message.actionCards && message.actionCards.length > 0 && (
                      <div className="flex flex-col gap-2 mt-2 border-t pt-2 border-border/50">
                        {message.actionCards.map((card, idx) => {
                          const isWhatsApp = card.type === 'draft_interest' || card.type === 'draft_negotiation';
                          const isOrder = card.type === 'draft_order';
                          const isTask = card.type === 'add_task';

                          const handleAction = async () => {
                            if (isWhatsApp) {
                              const yes = await showConfirm({
                                title: 'Send WhatsApp Message?',
                                message: 'This will automatically send a WhatsApp message to the supplier via Twilio.',
                                details: {
                                  supplier: card.data?.supplier?.supplier_name || card.data?.supplier?.name || 'Supplier',
                                  product: card.data?.product,
                                },
                              });
                              if (!yes) return;
                              try {
                                await apiClient.post('/api/whatsapp/contact-supplier', {
                                  supplierName: card.data?.supplier?.supplier_name || card.data?.supplier?.name || 'Supplier',
                                  supplierPhone: card.data?.supplier?.contact,
                                  productName: card.data?.product || 'Products',
                                  message: card.data?.message_draft,
                                });
                                toast.success('Message sent via WhatsApp!');
                              } catch (e) {
                                toast.error('Failed to send WhatsApp message');
                              }
                            } else if (isOrder) {
                              const yes = await showConfirm({
                                title: 'Create Purchase Order?',
                                message: 'This will create a new purchase order in the system.',
                                details: {
                                  supplier: card.data?.supplier || 'Unknown Supplier',
                                  product: card.data?.product || 'General',
                                  quantity: card.data?.quantity || 1,
                                  total_cost: card.data?.total_cost ? `Rs.${card.data.total_cost}` : 'TBD',
                                },
                              });
                              if (!yes) return;
                              try {
                                const orderData = {
                                  supplier: card.data?.supplier || 'Unknown Supplier',
                                  total_amount: card.data?.total_cost || 0,
                                  items: [{
                                    product_name: card.data?.product || 'General',
                                    quantity: card.data?.quantity || 1,
                                    unit_price: card.data?.price_per_unit || 0,
                                  }],
                                  status: 'Pending',
                                  store_id: 'store001',
                                };
                                await supplierApi.addPurchaseOrder(orderData);
                                toast.success('Order created successfully!');
                              } catch (e) {
                                toast.error('Failed to create order');
                              }
                            } else if (isTask) {
                              const taskText = card.data?.task_text || card.title || 'New Task from AI';
                              window.dispatchEvent(new CustomEvent('taskAdded', { detail: taskText }));
                              toast.success('Task added to Dashboard!');
                            }
                          };

                          return (
                            <Card key={idx} className="p-3 bg-card border-primary/20 shadow-sm">
                              <div className="flex items-center gap-2 mb-2">
                                <CheckCircle2 className="w-4 h-4 text-primary" />
                                <span className="font-semibold text-xs uppercase text-primary tracking-wide">
                                  {card.type.replace(/_/g, ' ')}
                                </span>
                              </div>
                              <p className="text-sm text-foreground mb-3">{card.title}</p>
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  variant="default"
                                  className="flex-1 text-xs h-8"
                                  onClick={handleAction}
                                >
                                  {isWhatsApp ? 'Send on WhatsApp' : isOrder ? 'Create Order' : isTask ? 'Add to Dashboard' : 'Execute Action'}
                                </Button>
                              </div>
                            </Card>
                          );
                        })}
                      </div>
                    )}

                    {/* Alerts */}
                    {message.alerts && message.alerts.length > 0 && (
                      <div className="flex flex-col gap-2 mt-1">
                        {message.alerts.map((alert, idx) => (
                          <div key={idx} className="flex items-start gap-2 bg-amber-500/10 text-amber-600 p-2 rounded-md border border-amber-500/20 text-xs">
                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                            <span>{alert.message}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </Card>
                  <p className="text-xs opacity-70 mt-1">
                    {new Date(message.timestamp).toLocaleTimeString()}
                  </p>
                </motion.div>
              ))}

              {/* Typing indicator */}
              {isTyping && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3"
                >
                  <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
                    <Bot className="h-4 w-4" />
                  </div>
                  <Card className="p-3 bg-accent/10 border-accent/30 rounded-2xl rounded-tl-sm flex items-center gap-1">
                    <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0 }} />
                    <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }} />
                    <motion.div className="w-2 h-2 rounded-full bg-muted-foreground" animate={{ y: [0, -5, 0] }} transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }} />
                  </Card>
                </motion.div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Suggested Prompts */}
            <div className="px-4 py-2 border-t border-border">
              <p className="text-xs text-muted-foreground mb-2">Suggested:</p>
              <div className="flex gap-2 flex-wrap">
                {suggestedPrompts.map((prompt) => (
                  <Button
                    key={prompt}
                    variant="outline"
                    size="sm"
                    className="text-xs"
                    onClick={() => setInputValue(prompt)}
                  >
                    {prompt}
                  </Button>
                ))}
              </div>
            </div>

            {/* Input */}
            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Input
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Ask me anything..."
                  className="flex-1"
                />
                <Button size="icon" onClick={handleSendMessage} disabled={!inputValue.trim() || isTyping}>
                  <Send className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </>
  );
};

export default ChatPanel;
