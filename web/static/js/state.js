// state.js - 全局状态管理

let sessions = [];
let localSessions = [];
let remoteHostSessions = {};
let remoteHosts = [];
let allTasks = [];
let bookmarks = [];
let notes = {};
let requirements = [];
let requirementsDetailCache = {};
let archivedSessions = [];
let selectedProject = null;
let selectedSession = null;
let currentTab = 'overview';
let mainView = 'requirement';
let selectedReqCategory = 'all';
let selectedRequirement = null;

let currentHostTab = 'local';

let filters = {
    status: 'all',
    tool: 'all',
    subagent: 'all'
};

let expandedDirs = {};
let batchSelectMode = false;
let batchSelectedProject = null;
let mergedSuggestions = [];
