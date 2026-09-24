# Resume Maker

一个本地优先、开源、前后端分离的中文简历生成器。前端使用 React + Vite + TypeScript，后端使用 FastAPI + SQLite。

## 功能

- 左侧简历优化对话，右侧 A4 简历预览
- 支持在预览稿中点击文字直接修改，条目可排序或删除
- 专业 / 极简两套排版，6 种主题色
- 个人信息、工作经历、项目、教育、技能模块
- 浏览器自动保存，登录/云服务均非必需
- FastAPI REST API 与 SQLite 持久化
- 浏览器原生打印，可直接另存为 PDF
- 示例数据、完成度提示与响应式布局

## 快速开始

### 1. 启动后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

接口文档：<http://localhost:8000/docs>

### 2. 启动前端

打开另一个终端：

```bash
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。开发服务器会将 `/api` 请求代理到 FastAPI。

## 项目结构

```text
.
├── backend/              # FastAPI API、SQLite 数据层、测试
│   ├── app/
│   └── tests/
└── frontend/             # React + Vite 单页应用
    └── src/
        ├── components/
        ├── api.ts
        ├── types.ts
        └── styles.css
```

## 配置

前端生产环境可通过 `VITE_API_URL` 指定后端地址，例如：

```bash
VITE_API_URL=https://api.example.com npm run build
```

后端环境变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RESUME_DB_PATH` | `backend/data/resumes.db` | SQLite 文件路径 |
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | 允许的前端域名，逗号分隔 |

## 测试

```bash
cd backend && pytest
cd frontend && npm run build
```

## License

MIT
