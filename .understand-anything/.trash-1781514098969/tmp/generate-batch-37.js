const fs = require('fs');

const extractData = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-extract-results-37.json', 'utf-8'));
const importData = JSON.parse(fs.readFileSync('C:/SVN_CODE/branches/real/could_frontend/.understand-anything/tmp/ua-file-analyzer-input-37.json', 'utf-8')).batchImportData;

const nodes = [];
const edges = [];

const fileMetadata = {
  "backend/apps/resources/migrations/0011_navigationcommand_and_access_data.py": { sum: "Django 数据库迁移文件：添加导航命令及相关访问控制数据。", tags: ["database", "migration", "resources", "navigation"] },
  "backend/apps/resources/migrations/0012_point_workflow_steps.py": { sum: "Django 数据库迁移文件：修改点位的工作流步骤。", tags: ["database", "migration", "resources", "workflow"] },
  "backend/apps/resources/migrations/0013_remove_aliyun_command_menu.py": { sum: "Django 数据库迁移文件：移除阿里云命令相关菜单。", tags: ["database", "migration", "resources", "menu"] },
  "backend/apps/resources/migrations/0014_command_types_menu_tree.py": { sum: "Django 数据库迁移文件：更新命令类型菜单树结构。", tags: ["database", "migration", "resources", "menu"] },
  "backend/apps/resources/migrations/0015_backend_management_flow_schema.py": { sum: "Django 数据库迁移文件：添加后端管理流程相关的数据库表结构。", tags: ["database", "migration", "resources", "schema"] },
  "backend/apps/resources/migrations/0016_backend_management_flow_access.py": { sum: "Django 数据库迁移文件：配置后端管理流程的访问权限数据。", tags: ["database", "migration", "resources", "access"] },
  "backend/apps/resources/migrations/0017_taskcommandstep_delay_seconds.py": { sum: "Django 数据库迁移文件：为任务命令步骤添加延迟秒数（delay_seconds）字段。", tags: ["database", "migration", "resources"] },
  "backend/apps/resources/migrations/0018_resource_cloud_url.py": { sum: "Django 数据库迁移文件：为资源表添加云端 URL 字段。", tags: ["database", "migration", "resources"] },
  "backend/apps/resources/migrations/0019_resource_cloud_url_length.py": { sum: "Django 数据库迁移文件：调整资源云端 URL 字段的长度限制。", tags: ["database", "migration", "resources"] },
  "backend/apps/resources/migrations/0020_scrolling_text_and_access_data.py": { sum: "Django 数据库迁移文件：添加滚动字幕配置及相关访问数据。", tags: ["database", "migration", "resources", "scrolling-text"] },
  "backend/apps/resources/migrations/0021_taskcommandstep_image_text.py": { sum: "Django 数据库迁移文件：为任务命令步骤添加图文信息字段。", tags: ["database", "migration", "resources"] },
  "backend/apps/resources/migrations/0022_control_command_value_type.py": { sum: "Django 数据库迁移文件：添加控制命令的值类型字段。", tags: ["database", "migration", "resources", "command"] },
  "backend/apps/resources/migrations/0023_control_command_value_type_ascii.py": { sum: "Django 数据库迁移文件：更新控制命令值类型，支持 ASCII 等。", tags: ["database", "migration", "resources", "command"] },
  "backend/apps/resources/migrations/0024_taskcommandstep_inner_tasks.py": { sum: "Django 数据库迁移文件：为任务命令步骤添加内部任务列表字段。", tags: ["database", "migration", "resources", "task"] },
  "backend/apps/resources/migrations/0025_taskcommandstep_wait_for_inner_tasks.py": { sum: "Django 数据库迁移文件：为任务命令步骤添加是否等待内部任务完成的标志。", tags: ["database", "migration", "resources", "task"] },
  "backend/apps/resources/migrations/0026_taskcommandstep_is_show.py": { sum: "Django 数据库迁移文件：为任务命令步骤添加显示控制字段（is_show）。", tags: ["database", "migration", "resources", "task"] },
  "backend/apps/resources/migrations/0027_point_is_show.py": { sum: "Django 数据库迁移文件：为点位模型添加显示控制字段（is_show）。", tags: ["database", "migration", "resources"] },
  "backend/apps/resources/migrations/0028_commandgroup_tenant_controlcommand_tenant_and_more.py": { sum: "Django 数据库迁移文件：为命令组、控制命令等模型添加租户（tenant）关联。", tags: ["database", "migration", "resources", "tenant"] },
  "backend/apps/resources/migrations/0029_minio_config_and_resource_object_key.py": { sum: "Django 数据库迁移文件：添加 MinIO 配置及资源对象 key 字段。", tags: ["database", "migration", "resources", "minio"] },
  "backend/apps/resources/migrations/0030_resource_object_size_tenantvideoquota.py": { sum: "Django 数据库迁移文件：记录资源对象大小并添加租户视频配额表。", tags: ["database", "migration", "resources", "quota"] },
  "backend/apps/resources/migrations/0031_minioconfig_allow_video_cloud_url.py": { sum: "Django 数据库迁移文件：在 MinIO 配置中添加允许使用云端视频 URL 的选项。", tags: ["database", "migration", "resources", "minio"] },
  "backend/apps/resources/point_admin.py": { sum: "Django Admin 配置文件：注册点位（Point）模型到管理后台。", tags: ["admin", "configuration", "resources"] },
  "backend/apps/resources/services/__init__.py": { sum: "资源模块服务层的初始化入口文件。", tags: ["entry-point", "service", "resources"] },
  "backend/apps/resources/tests/__init__.py": { sum: "资源模块测试包的初始化入口文件。", tags: ["entry-point", "test", "resources"] },
  "backend/apps/resources/tests/test_admin_control_command.py": { sum: "测试文件：针对管理后台控制命令的单元测试。", tags: ["test", "admin", "resources", "command"] }
};

function getComplexity(lines) {
  if (lines > 200) return 'complex';
  if (lines > 50) return 'moderate';
  return 'simple';
}

function processBatch() {
  for (const file of extractData.results) {
    const p = file.path;
    const meta = fileMetadata[p] || { sum: "文件: " + p, tags: ["file"] };
    
    // Create file node
    nodes.push({
      id: "file:" + p,
      type: "file",
      name: p.split('/').pop(),
      filePath: p,
      summary: meta.sum,
      tags: meta.tags,
      complexity: getComplexity(file.nonEmptyLines)
    });

    // Create import edges
    if (importData[p]) {
      for (const imp of importData[p]) {
        edges.push({
          source: "file:" + p,
          target: "file:" + imp,
          type: "imports",
          direction: "forward",
          weight: 0.7
        });
      }
    }

    const exportedNames = new Set((file.exports || []).map(e => e.name));

    // Process functions
    const funcs = file.functions || [];
    for (const f of funcs) {
      const lines = f.endLine - f.startLine + 1;
      const isExported = exportedNames.has(f.name);
      if (lines >= 10 || isExported) {
        const fId = "function:" + p + ":" + f.name;
        nodes.push({
          id: fId,
          type: "function",
          name: f.name,
          filePath: p,
          lineRange: [f.startLine, f.endLine],
          summary: "函数：" + f.name + "，位于 " + p,
          tags: ["function", isExported ? "exported" : "internal"],
          complexity: getComplexity(lines)
        });
        
        edges.push({
          source: "file:" + p,
          target: fId,
          type: "contains",
          direction: "forward",
          weight: 1.0
        });

        if (isExported) {
          edges.push({
            source: "file:" + p,
            target: fId,
            type: "exports",
            direction: "forward",
            weight: 0.8
          });
        }
      }
    }

    // Process classes
    const classes = file.classes || [];
    for (const c of classes) {
      const lines = c.endLine - c.startLine + 1;
      const methods = c.methods ? c.methods.length : 0;
      const isExported = exportedNames.has(c.name);
      
      if (lines >= 20 || methods >= 2 || isExported) {
        const cId = "class:" + p + ":" + c.name;
        nodes.push({
          id: cId,
          type: "class",
          name: c.name,
          filePath: p,
          lineRange: [c.startLine, c.endLine],
          summary: "类：" + c.name + "，包含 " + methods + " 个方法。",
          tags: ["class", isExported ? "exported" : "internal"],
          complexity: getComplexity(lines)
        });

        edges.push({
          source: "file:" + p,
          target: cId,
          type: "contains",
          direction: "forward",
          weight: 1.0
        });

        if (isExported) {
          edges.push({
            source: "file:" + p,
            target: cId,
            type: "exports",
            direction: "forward",
            weight: 0.8
          });
        }
      }
    }
  }

  // Split and Write logic
  const batchIndex = 37;
  const nodeCount = nodes.length;
  const edgeCount = edges.length;

  const outDir = 'C:/SVN_CODE/branches/real/could_frontend/.understand-anything/intermediate';
  if (!fs.existsSync(outDir)) {
    fs.mkdirSync(outDir, { recursive: true });
  }

  if (nodeCount <= 60 && edgeCount <= 120) {
    fs.writeFileSync(outDir + '/batch-' + batchIndex + '.json', JSON.stringify({ nodes, edges }, null, 2), 'utf-8');
    console.log("Wrote 1 part. Total nodes:", nodeCount, "Total edges:", edgeCount);
  } else {
    const parts = Math.ceil(Math.max(nodeCount / 60, edgeCount / 120));
    
    // Sort files alphabetically by path
    const sortedFiles = extractData.results.map(r => r.path).sort();
    const filesPerPart = Math.ceil(sortedFiles.length / parts);
    
    for (let k = 1; k <= parts; k++) {
      const startIdx = (k - 1) * filesPerPart;
      const endIdx = k * filesPerPart;
      const partFiles = new Set(sortedFiles.slice(startIdx, endIdx));
      
      const partNodes = nodes.filter(n => partFiles.has(n.filePath));
      const partNodeIds = new Set(partNodes.map(n => n.id));
      
      const partEdges = edges.filter(e => partNodeIds.has(e.source));
      
      fs.writeFileSync(outDir + '/batch-' + batchIndex + '-part-' + k + '.json', JSON.stringify({ nodes: partNodes, edges: partEdges }, null, 2), 'utf-8');
      console.log(`Wrote part ${k}. Nodes: ${partNodes.length}, Edges: ${partEdges.length}`);
    }
    console.log("Wrote", parts, "parts. Total nodes:", nodeCount, "Total edges:", edgeCount);
  }
}

processBatch();
