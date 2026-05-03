import file from '@system.file'

export default class GameEngine {
  constructor() {
    this.scripts = {};                    // 脚本存储
    this.isLoaded = false;
    this.loadPromise = null;
    this.chunkSize = 500;
    this.maxRetries = 2;                  // 最大重试次数
    this.retryDelay = 150;
    
    // 内存管理
    this.loadedChunks = {};               // { chunkNumber: { loaded: true, retries: 0 } }
    this.currentChunk = 1;
    this.pendingLoads = {};               // { chunkNumber: promise }
    
    // 并发控制
    this.activeLoads = 0;
    this.maxConcurrentLoads = 2;          // 最多同时加载2个块
    this.loadQueue = [];
    
    this.totalScriptsCount = 0;
    this.lastMemoryCleanup = 0;
    this.cleanupInterval = 10000;         // 10秒清理一次旧块
  }

  async loadGameScript() {
    if (this.loadPromise) return this.loadPromise;
    if (this.isLoaded) return true;

    this.loadPromise = new Promise(async (resolve) => {
      try {
        console.log('[GameEngine] 启动极简加载模式');
        this.scripts = {};
        this.loadedChunks = {};
        this.pendingLoads = {};
        
        // 只强制加载第一个块（必须成功）
        const success = await this.loadMinimalChunk(1, true); // 强制重试直到成功
        if (!success) {
          throw new Error('无法加载初始脚本块');
        }
        
        this.isLoaded = true;
        console.log('[GameEngine] 游戏脚本就绪');
        resolve(true);
      } catch (error) {
        console.error('[GameEngine] 脚本加载失败，使用备用:', error);
        this.scripts = this.getEssentialScripts();
        this.isLoaded = true;
        resolve(true);
      } finally {
        this.loadPromise = null;
      }
    });
    return this.loadPromise;
  }

  // 加载指定块（带重试和并发排队）
  async loadMinimalChunk(chunkNumber, forceRetry = false) {
    // 如果已经成功加载过，直接返回
    if (this.loadedChunks[chunkNumber] && this.loadedChunks[chunkNumber].loaded === true) {
      return true;
    }
    
    // 如果正在加载中，返回已有的 Promise
    if (this.pendingLoads[chunkNumber]) {
      return this.pendingLoads[chunkNumber];
    }
    
    // 重试计数
    const retryCount = this.loadedChunks[chunkNumber]?.retries || 0;
    if (!forceRetry && retryCount >= this.maxRetries) {
      console.warn(`[GameEngine] 块 ${chunkNumber} 已达最大重试次数，跳过`);
      return false;
    }
    
    // 创建加载任务
    const loadTask = () => new Promise((resolve) => {
      const fileName = `/common/script/scriptData${chunkNumber}.txt`;
      console.log(`[GameEngine] 开始加载块 ${chunkNumber}`);
      
      file.readText({
        uri: fileName,
        success: (data) => {
          try {
            const jsonText = typeof data === 'string' ? data : (data.text || '');
            const chunkScripts = this.parseChunkMinimal(jsonText, chunkNumber);
            
            // 检查是否有效数据
            if (Object.keys(chunkScripts).length === 0 && chunkNumber !== 1) {
              throw new Error(`块 ${chunkNumber} 解析后为空`);
            }
            
            this.addScriptsSparse(chunkScripts);
            
            // 记录成功加载
            this.loadedChunks[chunkNumber] = {
              loaded: true,
              retries: 0,
              timestamp: Date.now()
            };
            this.totalScriptsCount += Object.keys(chunkScripts).length;
            console.log(`[GameEngine] 块 ${chunkNumber} 加载成功，新增 ${Object.keys(chunkScripts).length} 个脚本`);
            
            // 加载成功后尝试清理旧块（但不要太频繁）
            this.scheduleCleanup();
            
            resolve(true);
          } catch (error) {
            console.error(`[GameEngine] 处理块 ${chunkNumber} 失败:`, error);
            this.handleLoadError(chunkNumber);
            resolve(false);
          } finally {
            delete this.pendingLoads[chunkNumber];
            this.activeLoads--;
            this.processLoadQueue();
          }
        },
        fail: (error) => {
          console.error(`[GameEngine] 读取块 ${chunkNumber} 失败:`, error);
          this.handleLoadError(chunkNumber);
          resolve(false);
          delete this.pendingLoads[chunkNumber];
          this.activeLoads--;
          this.processLoadQueue();
        }
      });
    });
    
    // 队列控制
    if (this.activeLoads >= this.maxConcurrentLoads) {
      const queuePromise = new Promise((resolve) => {
        this.loadQueue.push(() => {
          loadTask().then(resolve);
        });
      });
      this.pendingLoads[chunkNumber] = queuePromise;
      return queuePromise;
    } else {
      this.activeLoads++;
      const promise = loadTask();
      this.pendingLoads[chunkNumber] = promise;
      return promise;
    }
  }
  
  // 处理加载错误（增加重试计数，但不标记为已加载）
  handleLoadError(chunkNumber) {
    const current = this.loadedChunks[chunkNumber];
    const newRetries = (current?.retries || 0) + 1;
    this.loadedChunks[chunkNumber] = {
      loaded: false,
      retries: newRetries,
      timestamp: Date.now()
    };
    console.warn(`[GameEngine] 块 ${chunkNumber} 加载失败，重试次数 ${newRetries}/${this.maxRetries}`);
  }
  
  // 处理加载队列
  processLoadQueue() {
    if (this.loadQueue.length > 0 && this.activeLoads < this.maxConcurrentLoads) {
      const next = this.loadQueue.shift();
      if (next) {
        this.activeLoads++;
        next();
      }
    }
  }
  
  // 延迟清理（避免频繁操作）
  scheduleCleanup() {
    const now = Date.now();
    if (now - this.lastMemoryCleanup > this.cleanupInterval) {
      this.lastMemoryCleanup = now;
      this.cleanupOldChunks(this.currentChunk);
    }
  }
  
  // 解析JSON（增强BOM处理和空内容判断）
  parseChunkMinimal(jsonText, chunkNumber) {
    if (!jsonText || jsonText.trim() === '') {
      console.warn(`[GameEngine] 块 ${chunkNumber} 内容为空`);
      return {};
    }
    
    let text = jsonText.trim();
    
    // 移除BOM
    if (text.charCodeAt(0) === 0xFEFF) {
      text = text.substring(1);
    }
    
    // 尝试解析
    try {
      if ((text.startsWith('{') && text.endsWith('}')) || (text.startsWith('[') && text.endsWith(']'))) {
        const parsed = JSON.parse(text);
        // 期望得到一个对象，键为字符串ID
        if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
          return parsed;
        } else {
          console.warn(`[GameEngine] 块 ${chunkNumber} 格式不是对象`);
          return {};
        }
      } else {
        console.warn(`[GameEngine] 块 ${chunkNumber} 不是有效的JSON格式`);
        return {};
      }
    } catch (e) {
      console.error(`[GameEngine] 块 ${chunkNumber} JSON解析错误:`, e.message);
      // 打印前100个字符以便调试
      console.log(`[GameEngine] 错误内容预览: ${text.substring(0, 100)}`);
      return {};
    }
  }
  
  addScriptsSparse(newScripts) {
    for (const key in newScripts) {
      if (newScripts.hasOwnProperty(key)) {
        this.scripts[key] = newScripts[key];
      }
    }
  }
  
  // 清理不需要的块（保留当前块及前后各一块）
  cleanupOldChunks(currentChunk) {
    const keepChunks = new Set([currentChunk, currentChunk - 1, currentChunk + 1]);
    let removedCount = 0;
    
    for (const chunkKey in this.loadedChunks) {
      const chunkNum = parseInt(chunkKey);
      if (!keepChunks.has(chunkNum) && this.loadedChunks[chunkNum]?.loaded === true) {
        // 从 scripts 中删除该块的所有脚本
        const startId = (chunkNum - 1) * this.chunkSize + 1;
        const endId = chunkNum * this.chunkSize;
        for (let id = startId; id <= endId; id++) {
          delete this.scripts[id.toString()];
        }
        delete this.loadedChunks[chunkKey];
        removedCount++;
      }
    }
    
    if (removedCount > 0) {
      console.log(`[GameEngine] 清理了 ${removedCount} 个旧块，当前块 ${currentChunk}`);
    }
  }
  
  // 按需加载当前进度相关的块
  async smartLoadForProgress(progressId) {
    if (!this.isLoaded) return;
    
    const targetChunk = Math.ceil(progressId / this.chunkSize);
    if (targetChunk !== this.currentChunk) {
      this.currentChunk = targetChunk;
    }
    
    // 加载当前块（如果未成功加载过且未超过重试次数）
    const chunkInfo = this.loadedChunks[targetChunk];
    if (!chunkInfo || chunkInfo.loaded !== true) {
      await this.loadMinimalChunk(targetChunk);
    }
    
    // 温和预加载（仅在当前块稳定后，且距离边界较近时）
    const positionInChunk = progressId % this.chunkSize || this.chunkSize;
    const preloadDistance = 15;  // 稍大的阈值，减少频繁触发
    
    if (positionInChunk >= this.chunkSize - preloadDistance) {
      const nextChunk = targetChunk + 1;
      const nextInfo = this.loadedChunks[nextChunk];
      if ((!nextInfo || nextInfo.loaded !== true) && (!this.pendingLoads[nextChunk])) {
        // 延迟预加载，避免影响当前操作
        setTimeout(() => this.loadMinimalChunk(nextChunk).catch(() => {}), 300);
      }
    } else if (positionInChunk <= preloadDistance && targetChunk > 1) {
      const prevChunk = targetChunk - 1;
      const prevInfo = this.loadedChunks[prevChunk];
      if ((!prevInfo || prevInfo.loaded !== true) && (!this.pendingLoads[prevChunk])) {
        setTimeout(() => this.loadMinimalChunk(prevChunk).catch(() => {}), 300);
      }
    }
  }
  
  async getScript(progressId) {
    const id = progressId.toString();
    
    if (!this.isLoaded) {
      return this.getFallbackScript(progressId);
    }
    
    // 确保相关块已尝试加载
    await this.smartLoadForProgress(progressId);
    
    const script = this.scripts[id];
    if (!script) {
      // 最后尝试：如果当前块加载失败但未重试满，立即强制重试一次
      const targetChunk = Math.ceil(progressId / this.chunkSize);
      const chunkInfo = this.loadedChunks[targetChunk];
      if (!chunkInfo || chunkInfo.loaded !== true) {
        console.log(`[GameEngine] 脚本 ${progressId} 缺失，尝试强制重载块 ${targetChunk}`);
        await this.loadMinimalChunk(targetChunk, true);
        // 再次获取
        const retryScript = this.scripts[id];
        if (retryScript) return this.formatScript(retryScript, progressId);
      }
      console.warn(`[GameEngine] 脚本 ${progressId} 最终不存在`);
      return this.getFallbackScript(progressId);
    }
    
    return this.formatScript(script, progressId);
  }
  
  formatScript(script, progressId) {
    return {
      id: progressId,
      background: script.b ? `/common/bcgi/${script.b}.jpg` : "",
      character: script.c ? `/common/cimg/${script.c}.png` : "",
      cg: script.cg ? `/common/evig/${script.cg}` : "",
      speaker: script.s || "",
      text: script.t || "",
      z: script.z || 0,
      choose: !!script.co,
      choose1: script.c1 || "",
      choose2: script.c2 || "",
      choose3: script.c3 || "",
      choose4: script.c4 || "",
      choose1To: script.c1t || progressId,
      choose2To: script.c2t || progressId,
      choose3To: script.c3t || progressId,
      choose4To: script.c4t || progressId
    };
  }
  
  getFallbackScript(progressId = 0) {
    return {
      id: progressId,
      background: "/common/bcgi/画面_白.jpg",
      character: "",
      cg: "",
      speaker: "系统",
      text: progressId > 0 ? `等待加载 ${progressId}` : "加载中...",
      z: 0,
      choose: false,
      choose1: "", choose2: "", choose3: "", choose4: "",
      choose1To: progressId, choose2To: progressId,
      choose3To: progressId, choose4To: progressId
    };
  }
  
  getEssentialScripts() {
    return {
      "1": { b: "演出_ライト2", s: "系统", t: "游戏启动中..." },
      "2": { b: "演出_ライト2", s: "", t: "请稍候..." },
      "3": { b: "演出_ライト2", s: "", t: "正在初始化..." }
    };
  }
  
  hasNext(progressId) {
    const nextId = (parseInt(progressId) + 1).toString();
    return this.scripts.hasOwnProperty(nextId);
  }
  
  getNextProgressId(progressId) {
    const nextId = parseInt(progressId) + 1;
    return this.scripts.hasOwnProperty(nextId.toString()) ? nextId : null;
  }
  
  getTotalProgress() {
    return this.totalScriptsCount;
  }
  
  forceCleanup() {
    this.cleanupOldChunks(this.currentChunk);
    // 额外清理 pending 队列
    this.loadQueue = [];
    console.log('[GameEngine] 强制内存清理完成');
  }
  
  getMemoryStatus() {
    const loadedChunksList = Object.keys(this.loadedChunks).filter(k => this.loadedChunks[k]?.loaded === true).map(k => parseInt(k));
    return {
      loadedChunks: loadedChunksList.length,
      totalScripts: this.totalScriptsCount,
      currentChunk: this.currentChunk,
      memory: `${Math.round(this.totalScriptsCount * 0.3)}KB`
    };
  }
  
  async preloadRange(startId, endId) {
    const startChunk = Math.ceil(startId / this.chunkSize);
    const endChunk = Math.ceil(endId / this.chunkSize);
    const maxPreload = 3;
    let loaded = 0;
    for (let chunk = startChunk; chunk <= endChunk && loaded < maxPreload; chunk++) {
      const info = this.loadedChunks[chunk];
      if (!info || info.loaded !== true) {
        await this.loadMinimalChunk(chunk);
        loaded++;
      }
    }
  }
  
  clearAll() {
    this.scripts = {};
    this.loadedChunks = {};
    this.pendingLoads = {};
    this.loadQueue = [];
    this.activeLoads = 0;
    this.totalScriptsCount = 0;
    this.isLoaded = false;
    console.log('[GameEngine] 所有内存已清空');
  }
}