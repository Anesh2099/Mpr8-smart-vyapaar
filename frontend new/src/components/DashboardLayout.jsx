import { Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import Sidebar from './Sidebar';
import ChatPanel from './ChatPanel/ChatPanel';
import { Toaster } from 'react-hot-toast';
import { Button } from './ui/button';
import { Bot, Sparkles } from 'lucide-react';
import useChatStore from '@/store/useChatStore';

const DashboardLayout = () => {
  const { isChatPanelOpen, toggleChatPanel } = useChatStore();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main Content - Shrinks when chat panel is open */}
      <motion.main 
        animate={{ 
          marginRight: isChatPanelOpen ? '0' : '0',
        }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className="flex-1 overflow-y-auto relative"
      >
        <Outlet />
        
        {/* Floating AI Button - Shows when panel is closed */}
        <AnimatePresence>
          {!isChatPanelOpen && (
            <motion.div
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ type: 'spring', damping: 20, stiffness: 300 }}
              className="fixed bottom-8 right-8 z-50"
            >
              <Button
                size="lg"
                onClick={toggleChatPanel}
                className="h-16 w-16 rounded-full shadow-2xl bg-gradient-to-br from-primary to-accent hover:from-primary/90 hover:to-accent/90 group relative overflow-hidden"
              >
                <div className="absolute inset-0 bg-gradient-to-r from-accent/20 to-primary/20 animate-pulse"></div>
                <div className="relative flex flex-col items-center justify-center">
                  <Bot className="h-7 w-7 mb-0.5" />
                  <Sparkles className="h-3 w-3 absolute -top-1 -right-1 text-accent animate-pulse" />
                </div>
              </Button>
              <div className="absolute -top-12 left-1/2 -translate-x-1/2 bg-card px-3 py-1.5 rounded-lg shadow-lg border border-border opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                <p className="text-sm font-medium">Ask AI Assistant</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.main>
      
      {/* Chat Panel - Integrated into flex layout */}
      <ChatPanel />
      
      {/* Toast Notifications */}
      <Toaster position="top-right" />
    </div>
  );
};

export default DashboardLayout;
