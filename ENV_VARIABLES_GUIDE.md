# 🔧 Hướng dẫn Thêm Biến Môi trường Mới

## 📝 Cách thêm biến môi trường mới vào project

### Bước 1: Thêm vào GitHub Secrets

Trong repository GitHub của bạn:

1. Vào **Settings** > **Secrets and variables** > **Actions**
2. Click **New repository secret**
3. Thêm secret mới, ví dụ:
   - Name: `NEW_VARIABLE_NAME`
   - Value: `your_secret_value`

### Bước 2: Cập nhật GitHub Actions workflow

Trong file `.github/workflows/deploy.yml`, thêm đoạn code sau vào phần environment variables:

```yaml
# Thêm vào cuối danh sách các biến môi trường
if [ -n "${{ secrets.NEW_VARIABLE_NAME }}" ]; then
  update_env_var "NEW_VARIABLE_NAME" "${{ secrets.NEW_VARIABLE_NAME }}"
fi
```

### Bước 3: Sử dụng trong ứng dụng

Trong code Python của bạn:

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Sử dụng biến môi trường
new_value = os.getenv('NEW_VARIABLE_NAME', 'default_value')
```

## 🔄 Ví dụ cụ thể

### Thêm biến REDIS_URL:

1. **GitHub Secrets:**
   ```
   Name: REDIS_URL
   Value: redis://localhost:6379/0
   ```

2. **Trong deploy.yml:**
   ```yaml
   if [ -n "${{ secrets.REDIS_URL }}" ]; then
     update_env_var "REDIS_URL" "${{ secrets.REDIS_URL }}"
   fi
   ```

3. **Trong Python:**
   ```python
   import os
   redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
   ```

## 📋 Danh sách biến có sẵn

Các biến đã được cấu hình sẵn trong workflow:

### Bắt buộc:
- `PROJECT_ROOT` - Đường dẫn gốc của project

### Tùy chọn (chỉ thêm nếu có trong secrets):
- `GOOGLE_API_KEY` - Google AI API
- `DEEPSEEK_API_KEY` - DeepSeek API  
- `GROK_API_KEY` - Grok API
- `SUPABASE_URL` - Supabase database URL
- `SUPABASE_KEY` - Supabase API key
- `POSTGRES_URL` - PostgreSQL connection string
- `CHATBOT_API_KEY` - Chatbot API key
- `OPENAI_API_KEY` - OpenAI API key
- `GOOGLE_SHEET_ID` - Google Sheets ID
- `JWT_SECRET` - JWT secret key
- `APP_SECRET_KEY` - Application secret key

## 🚀 Quy trình thêm biến mới

1. **Thêm secret vào GitHub repository**
2. **Cập nhật deploy.yml** với đoạn code check và update biến
3. **Push code lên main branch**  
4. **GitHub Actions sẽ tự động deploy** với biến mới
5. **Sử dụng biến trong code** với `os.getenv()`

## ⚠️ Lưu ý quan trọng

1. **Không commit secrets vào code** - Luôn sử dụng GitHub Secrets
2. **Backup file .env** - Workflow tự động backup trước khi cập nhật
3. **Kiểm tra logs** - Xem deployment logs để đảm bảo biến được thêm thành công
4. **Test locally** - Test với file .env local trước khi deploy

## 🔍 Kiểm tra biến đã được thêm

Sau khi deploy, kiểm tra trên server:

```bash
cd /your/project/path/chatbot_base
cat .env | grep YOUR_VARIABLE_NAME
```

Hoặc trong Python:

```python
import os
print(f"Variable value: {os.getenv('YOUR_VARIABLE_NAME', 'Not found')}")
```

## 📚 Ví dụ các biến thường dùng

```yaml
# Email configuration
if [ -n "${{ secrets.SMTP_HOST }}" ]; then
  update_env_var "SMTP_HOST" "${{ secrets.SMTP_HOST }}"
fi

# Redis cache
if [ -n "${{ secrets.REDIS_URL }}" ]; then
  update_env_var "REDIS_URL" "${{ secrets.REDIS_URL }}"
fi

# Third-party APIs
if [ -n "${{ secrets.STRIPE_API_KEY }}" ]; then
  update_env_var "STRIPE_API_KEY" "${{ secrets.STRIPE_API_KEY }}"
fi

# Custom app settings
if [ -n "${{ secrets.DEBUG_MODE }}" ]; then
  update_env_var "DEBUG_MODE" "${{ secrets.DEBUG_MODE }}"
fi
```

---

✅ **Với cách này, bạn có thể dễ dàng thêm bất kỳ biến môi trường nào mà không cần sửa đổi nhiều!**