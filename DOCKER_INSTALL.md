# Docker 安装指南

## Windows 11 Home 安装步骤

### 第一步：启用WSL2

1. **以管理员身份打开PowerShell**

2. **启用WSL功能**
   ```powershell
   wsl --install
   ```

3. **重启电脑**

4. **设置WSL2为默认版本**
   ```powershell
   wsl --set-default-version 2
   ```

5. **安装Ubuntu（如果提示）**
   ```powershell
   wsl --install -d Ubuntu
   ```

### 第二步：安装Docker Desktop

1. **下载Docker Desktop**
   - 访问: https://www.docker.com/products/docker-desktop
   - 点击 "Download for Windows"

2. **运行安装程序**
   - 双击下载的 `Docker Desktop Installer.exe`
   - 勾选 "Use WSL 2 instead of Hyper-V"
   - 点击 "OK" 开始安装

3. **启动Docker Desktop**
   - 安装完成后，双击桌面的Docker图标
   - 等待Docker启动（系统托盘显示鲸鱼图标）

4. **验证安装**
   ```powershell
   docker --version
   docker compose version
   ```

### 第三步：配置Docker Desktop

1. **打开Docker Desktop设置**
   - 点击系统托盘的鲸鱼图标
   - 选择 "Settings"

2. **资源配置**
   - 进入 "Resources" → "WSL Integration"
   - 确保Ubuntu已启用

3. **镜像加速（可选）**
   - 进入 "Docker Engine"
   - 添加以下配置:
   ```json
   {
     "registry-mirrors": [
       "https://docker.mirrors.ustc.edu.cn",
       "https://hub-mirror.c.163.com"
     ]
   }
   ```

4. **应用并重启Docker**

---

## 部署RAG系统

### 1. 进入项目目录
```powershell
cd D:\AI\project\rag-system
```

### 2. 使用部署脚本
```powershell
.\scripts\deploy.bat
```

### 3. 或手动启动
```powershell
# 构建并启动
docker compose --env-file .env.docker up -d

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 4. 访问服务
- **前端页面**: http://localhost
- **API文档**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/health

---

## 常用命令

```powershell
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f

# 进入容器
docker exec -it rag-app bash

# 查看容器状态
docker compose ps

# 重建镜像
docker compose build --no-cache
```

---

## 故障排除

### 问题1：WSL2安装失败
**解决方案：**
1. 启用虚拟化（BIOS设置）
2. 启用Hyper-V：
   ```powershell
   dism.exe /Online /Enable-Feature /All /FeatureName:Microsoft-Hyper-V
   ```

### 问题2：Docker启动慢
**解决方案：**
1. 增加Docker内存分配（建议4GB+）
2. 关闭不必要的后台程序

### 问题3：端口被占用
**解决方案：**
1. 修改 `.env.docker` 中的端口配置
2. 或停止占用端口的服务

### 问题4：镜像拉取慢
**解决方案：**
1. 配置镜像加速器（见上方配置）
2. 或使用VPN

---

## 卸载Docker

1. 打开 "设置" → "应用" → "应用和功能"
2. 找到 "Docker Desktop" 并卸载
3. 删除WSL发行版（可选）：
   ```powershell
   wsl --unregister docker-desktop
   wsl --unregister docker-desktop-data
   ```
