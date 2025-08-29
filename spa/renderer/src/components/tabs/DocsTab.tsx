import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  TextField,
  InputAdornment,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Drawer,
  AppBar,
  Toolbar,
  IconButton,
  Chip,
  Collapse,
  Alert,
  CircularProgress,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Search as SearchIcon,
  Description as FileIcon,
  Folder as FolderIcon,
  FolderOpen as FolderOpenIcon,
  ExpandLess,
  ExpandMore,
  MenuBook as DocsIcon,
  List as TocIcon,
  Menu as MenuIcon,
  Close as CloseIcon,
  Home as HomeIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus, vs } from 'react-syntax-highlighter/dist/esm/styles/prism';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import axios from 'axios';

// Types
interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  children?: FileNode[];
}

interface TableOfContentsItem {
  title: string;
  level: number;
  id: string;
}

// File tree structure for the repository
const fileTree: FileNode[] = [
  {
    name: 'README.md',
    path: 'README.md',
    type: 'file'
  },
  {
    name: 'CLAUDE.md',
    path: 'CLAUDE.md',
    type: 'file'
  },
  {
    name: 'CLI_COMMANDS.md',
    path: 'CLI_COMMANDS.md',
    type: 'file'
  },
  {
    name: 'GRAPH_ENRICHMENT_PLAN.md',
    path: 'GRAPH_ENRICHMENT_PLAN.md',
    type: 'file'
  },
  {
    name: 'IMPLEMENTATION_SUMMARY.md',
    path: 'IMPLEMENTATION_SUMMARY.md',
    type: 'file'
  },
  {
    name: 'PR-98-review-improvements.md',
    path: 'PR-98-review-improvements.md',
    type: 'file'
  },
  {
    name: 'docs',
    path: 'docs',
    type: 'directory',
    children: [
      {
        name: 'ARCHITECTURE_IMPROVEMENTS.md',
        path: 'docs/ARCHITECTURE_IMPROVEMENTS.md',
        type: 'file'
      },
      {
        name: 'fix-plan-api-versions.md',
        path: 'docs/fix-plan-api-versions.md',
        type: 'file'
      },
      {
        name: 'implementation-plan-properties-extraction.md',
        path: 'docs/implementation-plan-properties-extraction.md',
        type: 'file'
      },
      {
        name: 'threat_model_agent_demo.md',
        path: 'docs/threat_model_agent_demo.md',
        type: 'file'
      },
      {
        name: 'demo',
        path: 'docs/demo',
        type: 'directory',
        children: [
          {
            name: 'overview.md',
            path: 'docs/demo/overview.md',
            type: 'file'
          },
          {
            name: 'subset_bicep_demo.md',
            path: 'docs/demo/subset_bicep_demo.md',
            type: 'file'
          },
          {
            name: 'commands',
            path: 'docs/demo/commands',
            type: 'directory',
            children: [
              { name: 'README.md', path: 'docs/demo/commands/README.md', type: 'file' },
              { name: 'agent-mode.md', path: 'docs/demo/commands/agent-mode.md', type: 'file' },
              { name: 'backup-db.md', path: 'docs/demo/commands/backup-db.md', type: 'file' },
              { name: 'build.md', path: 'docs/demo/commands/build.md', type: 'file' },
              { name: 'config.md', path: 'docs/demo/commands/config.md', type: 'file' },
              { name: 'create-tenant-sample.md', path: 'docs/demo/commands/create-tenant-sample.md', type: 'file' },
              { name: 'create-tenant.md', path: 'docs/demo/commands/create-tenant.md', type: 'file' },
              { name: 'doctor.md', path: 'docs/demo/commands/doctor.md', type: 'file' },
              { name: 'generate-iac.md', path: 'docs/demo/commands/generate-iac.md', type: 'file' },
              { name: 'generate-sim-doc.md', path: 'docs/demo/commands/generate-sim-doc.md', type: 'file' },
              { name: 'generate-spec.md', path: 'docs/demo/commands/generate-spec.md', type: 'file' },
              { name: 'mcp-server.md', path: 'docs/demo/commands/mcp-server.md', type: 'file' },
              { name: 'spec.md', path: 'docs/demo/commands/spec.md', type: 'file' },
              { name: 'test.md', path: 'docs/demo/commands/test.md', type: 'file' },
              { name: 'threat-model.md', path: 'docs/demo/commands/threat-model.md', type: 'file' },
              { name: 'visualize.md', path: 'docs/demo/commands/visualize.md', type: 'file' },
            ]
          }
        ]
      },
      {
        name: 'design',
        path: 'docs/design',
        type: 'directory',
        children: [
          { name: 'SPA_ARCHITECTURE.md', path: 'docs/design/SPA_ARCHITECTURE.md', type: 'file' },
          { name: 'SPA_REQUIREMENTS.md', path: 'docs/design/SPA_REQUIREMENTS.md', type: 'file' },
          { name: 'iac_subset_bicep.md', path: 'docs/design/iac_subset_bicep.md', type: 'file' },
          { name: 'resource_processing_efficiency.md', path: 'docs/design/resource_processing_efficiency.md', type: 'file' },
        ]
      },
      {
        name: 'resources',
        path: 'docs/resources',
        type: 'directory',
        children: [
          { name: 'CloudThreatModelling.md', path: 'docs/resources/CloudThreatModelling.md', type: 'file' }
        ]
      }
    ]
  },
  {
    name: 'spa',
    path: 'spa',
    type: 'directory',
    children: [
      {
        name: 'docs',
        path: 'spa/docs',
        type: 'directory',
        children: [
          { name: 'GRAPH_VISUALIZATION.md', path: 'spa/docs/GRAPH_VISUALIZATION.md', type: 'file' }
        ]
      }
    ]
  },
  {
    name: 'dotnet',
    path: 'dotnet',
    type: 'directory',
    children: [
      { name: 'REMOVED_TESTS.md', path: 'dotnet/REMOVED_TESTS.md', type: 'file' }
    ]
  }
];

const DRAWER_WIDTH = 320;

// File tree component
interface FileTreeItemProps {
  node: FileNode;
  level: number;
  selectedFile: string | null;
  expandedFolders: Set<string>;
  searchQuery: string;
  onFileSelect: (path: string) => void;
  onFolderToggle: (path: string) => void;
}

const FileTreeItem: React.FC<FileTreeItemProps> = ({
  node,
  level,
  selectedFile,
  expandedFolders,
  searchQuery,
  onFileSelect,
  onFolderToggle,
}) => {
  const theme = useTheme();
  const isExpanded = expandedFolders.has(node.path);
  const isSelected = selectedFile === node.path;
  const matchesSearch = !searchQuery || 
    node.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    node.path.toLowerCase().includes(searchQuery.toLowerCase());

  // For folders, check if any children match the search
  const hasMatchingChildren = useMemo(() => {
    if (!searchQuery || node.type === 'file') return true;
    
    const checkChildren = (children: FileNode[]): boolean => {
      return children.some(child => 
        child.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        child.path.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (child.children && checkChildren(child.children))
      );
    };
    
    return node.children ? checkChildren(node.children) : false;
  }, [node, searchQuery]);

  if (!matchesSearch && !hasMatchingChildren) {
    return null;
  }

  if (node.type === 'file') {
    return (
      <ListItem disablePadding sx={{ display: 'block' }}>
        <ListItemButton
          selected={isSelected}
          onClick={() => onFileSelect(node.path)}
          sx={{
            pl: 2 + level * 2,
            minHeight: 36,
            '&.Mui-selected': {
              backgroundColor: alpha(theme.palette.primary.main, 0.12),
              '&:hover': {
                backgroundColor: alpha(theme.palette.primary.main, 0.18),
              },
            },
          }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            <FileIcon fontSize="small" />
          </ListItemIcon>
          <ListItemText
            primary={node.name}
            primaryTypographyProps={{ 
              variant: 'body2',
              noWrap: true,
              title: node.name
            }}
          />
        </ListItemButton>
      </ListItem>
    );
  }

  return (
    <>
      <ListItem disablePadding sx={{ display: 'block' }}>
        <ListItemButton
          onClick={() => onFolderToggle(node.path)}
          sx={{
            pl: 2 + level * 2,
            minHeight: 36,
          }}
        >
          <ListItemIcon sx={{ minWidth: 32 }}>
            {isExpanded ? <FolderOpenIcon fontSize="small" /> : <FolderIcon fontSize="small" />}
          </ListItemIcon>
          <ListItemText
            primary={node.name}
            primaryTypographyProps={{ 
              variant: 'body2',
              fontWeight: 500,
              noWrap: true,
              title: node.name
            }}
          />
          {isExpanded ? <ExpandLess /> : <ExpandMore />}
        </ListItemButton>
      </ListItem>
      <Collapse in={isExpanded} timeout="auto" unmountOnExit>
        <List component="div" disablePadding>
          {node.children?.map((child) => (
            <FileTreeItem
              key={child.path}
              node={child}
              level={level + 1}
              selectedFile={selectedFile}
              expandedFolders={expandedFolders}
              searchQuery={searchQuery}
              onFileSelect={onFileSelect}
              onFolderToggle={onFolderToggle}
            />
          ))}
        </List>
      </Collapse>
    </>
  );
};

// Table of contents component
const TableOfContents: React.FC<{ content: string; onItemClick: (id: string) => void }> = ({ 
  content, 
  onItemClick 
}) => {
  const toc = useMemo(() => {
    const headingRegex = /^(#{1,6})\s+(.+)$/gm;
    const items: TableOfContentsItem[] = [];
    let match;

    while ((match = headingRegex.exec(content)) !== null) {
      const level = match[1].length;
      const title = match[2].trim();
      const id = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
      
      items.push({ title, level, id });
    }

    return items;
  }, [content]);

  if (toc.length === 0) return null;

  return (
    <Paper sx={{ p: 2, mb: 2 }}>
      <Typography variant="subtitle2" gutterBottom sx={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 1 }}>
        <TocIcon fontSize="small" />
        Table of Contents
      </Typography>
      <List dense>
        {toc.map((item, index) => (
          <ListItem key={index} disablePadding>
            <ListItemButton
              onClick={() => onItemClick(item.id)}
              sx={{
                pl: (item.level - 1) * 2,
                py: 0.5,
                minHeight: 'auto',
              }}
            >
              <ListItemText
                primary={item.title}
                primaryTypographyProps={{
                  variant: 'body2',
                  fontSize: Math.max(0.75, 0.875 - (item.level - 1) * 0.1),
                  color: 'text.secondary',
                }}
              />
            </ListItemButton>
          </ListItem>
        ))}
      </List>
    </Paper>
  );
};

const DocsTab: React.FC = () => {
  const theme = useTheme();
  const [selectedFile, setSelectedFile] = useState<string | null>('README.md');
  const [fileContent, setFileContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [contentSearchQuery, setContentSearchQuery] = useState<string>('');
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(
    new Set(['docs', 'docs/demo', 'docs/design', 'spa', 'spa/docs'])
  );
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load file content
  const loadFile = useCallback(async (filePath: string) => {
    setLoading(true);
    setError(null);
    
    try {
      const url = `http://localhost:3001/api/docs/${encodeURIComponent(filePath)}`;
      const response = await axios.get(url);
      
      if (typeof response.data === 'string') {
        setFileContent(response.data);
      } else {
        console.error('DocsTab: Unexpected response format for file:', filePath, response.data);
        setError(`Unexpected response format for file: ${filePath}`);
        setFileContent('');
      }
    } catch (err) {
      console.error('DocsTab: Error loading file:', filePath, err);
      if (axios.isAxiosError(err)) {
        const statusCode = err.response?.status;
        const errorMessage = err.response?.data?.error || err.message;
        const errorPath = err.response?.data?.path;
        
        let detailedError = `Failed to load file: ${filePath}`;
        if (statusCode) detailedError += ` (${statusCode})`;
        if (errorMessage) detailedError += `: ${errorMessage}`;
        if (errorPath) detailedError += ` at ${errorPath}`;
        
        setError(detailedError);
      } else {
        setError(`Failed to load file: ${filePath} - ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
      setFileContent('');
    } finally {
      setLoading(false);
    }
  }, []);

  // Load initial file
  useEffect(() => {
    if (selectedFile) {
      loadFile(selectedFile);
    }
  }, [selectedFile, loadFile]);

  const handleFileSelect = (path: string) => {
    setSelectedFile(path);
    setContentSearchQuery('');
  };

  const handleFolderToggle = (path: string) => {
    const newExpanded = new Set(expandedFolders);
    if (newExpanded.has(path)) {
      newExpanded.delete(path);
    } else {
      newExpanded.add(path);
    }
    setExpandedFolders(newExpanded);
  };

  const scrollToHeading = (id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  // Highlight search results in content
  const highlightContent = useMemo(() => {
    if (!contentSearchQuery || !fileContent) return fileContent;
    
    const regex = new RegExp(`(${contentSearchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return fileContent.replace(regex, '**$1**');
  }, [fileContent, contentSearchQuery]);

  // Custom markdown components
  const markdownComponents = {
    code({ node, inline, className, children, ...props }: any) {
      const match = /language-(\w+)/.exec(className || '');
      
      if (!inline && match) {
        return (
          <SyntaxHighlighter
            style={theme.palette.mode === 'dark' ? vscDarkPlus : vs}
            language={match[1]}
            PreTag="div"
            {...props}
          >
            {String(children).replace(/\n$/, '')}
          </SyntaxHighlighter>
        );
      }
      
      return (
        <code className={className} {...props} style={{
          backgroundColor: alpha(theme.palette.text.primary, 0.05),
          padding: '2px 4px',
          borderRadius: '3px',
          fontSize: '0.875em',
        }}>
          {children}
        </code>
      );
    },
    h1: ({ children, ...props }: any) => (
      <Typography variant="h3" component="h1" gutterBottom sx={{ mt: 4, mb: 2 }} {...props}>
        {children}
      </Typography>
    ),
    h2: ({ children, ...props }: any) => (
      <Typography variant="h4" component="h2" gutterBottom sx={{ mt: 3, mb: 2 }} {...props}>
        {children}
      </Typography>
    ),
    h3: ({ children, ...props }: any) => (
      <Typography variant="h5" component="h3" gutterBottom sx={{ mt: 2, mb: 1 }} {...props}>
        {children}
      </Typography>
    ),
    h4: ({ children, ...props }: any) => (
      <Typography variant="h6" component="h4" gutterBottom sx={{ mt: 2, mb: 1 }} {...props}>
        {children}
      </Typography>
    ),
    h5: ({ children, ...props }: any) => (
      <Typography variant="subtitle1" component="h5" gutterBottom sx={{ mt: 1, mb: 1, fontWeight: 600 }} {...props}>
        {children}
      </Typography>
    ),
    h6: ({ children, ...props }: any) => (
      <Typography variant="subtitle2" component="h6" gutterBottom sx={{ mt: 1, mb: 1, fontWeight: 600 }} {...props}>
        {children}
      </Typography>
    ),
    p: ({ children, ...props }: any) => (
      <Typography variant="body1" paragraph {...props}>
        {children}
      </Typography>
    ),
    a: ({ href, children, ...props }: any) => {
      // Handle internal links
      if (href && href.endsWith('.md')) {
        return (
          <Box
            component="a"
            href="#"
            onClick={(e) => {
              e.preventDefault();
              const fullPath = href.startsWith('/') ? href.slice(1) : href;
              setSelectedFile(fullPath);
            }}
            sx={{
              color: 'primary.main',
              textDecoration: 'underline',
              cursor: 'pointer',
              '&:hover': { color: 'primary.dark' }
            }}
            {...props}
          >
            {children}
          </Box>
        );
      }
      
      return (
        <Box
          component="a"
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          sx={{
            color: 'primary.main',
            textDecoration: 'underline',
            '&:hover': { color: 'primary.dark' }
          }}
          {...props}
        >
          {children}
        </Box>
      );
    },
  };

  const drawerContent = (
    <Box sx={{ overflow: 'auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <DocsIcon />
          Documentation
        </Typography>
        
        <TextField
          fullWidth
          size="small"
          placeholder="Search files..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" />
              </InputAdornment>
            ),
          }}
          sx={{ mb: 1 }}
        />
        
        {selectedFile && (
          <Chip
            icon={<HomeIcon />}
            label={selectedFile.split('/').pop()}
            variant="outlined"
            size="small"
            sx={{ mr: 1 }}
          />
        )}
      </Box>
      
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        <List>
          {fileTree.map((node) => (
            <FileTreeItem
              key={node.path}
              node={node}
              level={0}
              selectedFile={selectedFile}
              expandedFolders={expandedFolders}
              searchQuery={searchQuery}
              onFileSelect={handleFileSelect}
              onFolderToggle={handleFolderToggle}
            />
          ))}
        </List>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', height: '100%' }}>
      {/* Sidebar */}
      <Drawer
        variant="persistent"
        anchor="left"
        open={sidebarOpen}
        sx={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: DRAWER_WIDTH,
            position: 'relative',
            height: '100%',
            border: 'none',
            borderRight: 1,
            borderColor: 'divider',
          },
        }}
      >
        {drawerContent}
      </Drawer>

      {/* Main content area */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          ml: sidebarOpen ? 0 : `-${DRAWER_WIDTH}px`,
          transition: theme.transitions.create(['margin'], {
            easing: theme.transitions.easing.sharp,
            duration: theme.transitions.duration.leavingScreen,
          }),
        }}
      >
        {/* Toolbar */}
        <AppBar position="static" elevation={0} sx={{ backgroundColor: 'background.paper', borderBottom: 1, borderColor: 'divider' }}>
          <Toolbar variant="dense">
            <IconButton
              edge="start"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              sx={{ mr: 2 }}
            >
              {sidebarOpen ? <CloseIcon /> : <MenuIcon />}
            </IconButton>
            
            <Typography variant="subtitle1" component="div" sx={{ flexGrow: 1, color: 'text.primary' }}>
              {selectedFile || 'Select a document'}
            </Typography>
            
            <TextField
              size="small"
              placeholder="Search in document..."
              value={contentSearchQuery}
              onChange={(e) => setContentSearchQuery(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
              sx={{ width: 250 }}
            />
          </Toolbar>
        </AppBar>

        {/* Content */}
        <Box sx={{ flex: 1, overflow: 'auto', display: 'flex' }}>
          {/* Table of contents */}
          {fileContent && !loading && (
            <Box sx={{ width: 250, p: 2, borderRight: 1, borderColor: 'divider', overflow: 'auto' }}>
              <TableOfContents content={fileContent} onItemClick={scrollToHeading} />
            </Box>
          )}
          
          {/* Document content */}
          <Box sx={{ flex: 1, p: 3, overflow: 'auto' }}>
            {loading && (
              <Box display="flex" justifyContent="center" alignItems="center" minHeight="200px">
                <CircularProgress />
              </Box>
            )}
            
            {error && (
              <Alert severity="error" sx={{ mb: 2 }}>
                {error}
              </Alert>
            )}
            
            {!loading && !error && !selectedFile && (
              <Box textAlign="center" py={8}>
                <DocsIcon sx={{ fontSize: 64, color: 'text.disabled', mb: 2 }} />
                <Typography variant="h5" color="text.secondary" gutterBottom>
                  Welcome to Documentation
                </Typography>
                <Typography variant="body1" color="text.secondary">
                  Select a document from the sidebar to start reading
                </Typography>
              </Box>
            )}
            
            {!loading && !error && fileContent && (
              <Paper sx={{ p: 3, backgroundColor: 'background.paper' }}>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeRaw]}
                  components={markdownComponents}
                >
                  {highlightContent}
                </ReactMarkdown>
              </Paper>
            )}
          </Box>
        </Box>
      </Box>
    </Box>
  );
};

export default DocsTab;