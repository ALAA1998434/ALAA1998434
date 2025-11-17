import telebot
import os
import json
import time
from datetime import datetime
import logging

# ******************************************************
# 🔧 CONFIGURATION SETTINGS
# ******************************************************
# يفضل استخدام متغيرات البيئة للاستضافة (مثل Railway)
API_TOKEN = os.environ.get('API_TOKEN', '8414443573:AAGKTy-VzJ-g9FzHubNah8niLqm6pb2BvPA')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '852713533'))

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DATA_FILE = os.path.join(BASE_DIR, 'data.json')
LOG_FILE = os.path.join(BASE_DIR, 'bot.log')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding='utf-8'), logging.StreamHandler()]
)

# ******************************************************
# 🎨 BOT MESSAGES
# ******************************************************
class BotMessages:
    WELCOME_ADMIN = "<b>🏛️ مرحباً بك في نظام إدارة المعهد</b>\n\n"
    WELCOME_STUDENT = "<b>🎓 مرحباً بك في المنصة التعليمية</b>\n\n"
    FILE_UPLOAD_START = "<b>📤 بدء رفع ملف جديد</b>\n⬆️ الرجاء إرسال ملف PDF\n↩️ رجوع للإلغاء"
    FILE_RECEIVED = "<b>✅ تم استلام الملف بنجاح</b>\n📝 اكتب اسم الملف:\n↩️ رجوع للإلغاء"
    FILE_NAME_SAVED = "<b>📝 تم حفظ الاسم</b>\n📂 اختر القسم المناسب:\n↩️ رجوع للإلغاء"
    FILE_UPLOAD_SUCCESS = "<b>🎉 تم رفع الملف بنجاح!</b>\n📄 <b>الاسم:</b> {name}\n📂 <b>القسم:</b> {subject}\n🆔 <b>المعرف:</b> {file_id}\n📦 <b>الحجم:</b> {size} م.ب\n🕒 <b>الوقت:</b> {time}"
    DELETE_START = "<b>🗑️ إدارة الأرشيف</b>\n🔢 أرسل معرف الملف للحذف\n↩️ رجوع للإلغاء"
    DELETE_SUCCESS = "<b>✅ تم الحذف</b>\n📄 <b>الاسم:</b> {name}\n🆔 <b>المعرف:</b> {file_id}"
    NO_FILES = "<b>📭 لا توجد ملفات متاحة حالياً</b>"
    NO_PERMISSION = "<b>🚫 غير مصرح بالوصول</b>"
    CANCELLED = "<b>❌ تم الإلغاء</b>"
    UNRECOGNIZED = "<b>❓ لم أفهم طلبك.</b> الرجاء استخدام الأزرار المتاحة."
# ******************************************************
# 🗃️ DATA MANAGEMENT
# ******************************************************
class DataManager:
    @staticmethod
    def load_data():
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # التأكد من وجود مفتاح stats
                if 'stats' not in data:
                     data['stats'] = {'total_uploads':0,'total_downloads':0,'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                return data
        except FileNotFoundError:
            default_data = {'files': [], 'next_id': 1, 'stats': {'total_uploads':0,'total_downloads':0,'last_activity': datetime.now().strftime("%Y-%m-%d %H:%M:%S")}}
            DataManager.save_data(default_data)
            return default_data
        except Exception as e:
            logging.error(f"خطأ في تحميل البيانات: {e}")
            return {'files': [], 'next_id':1, 'stats':{'total_uploads':0,'total_downloads':0}}

    @staticmethod
    def save_data(data):
        data['stats']['last_activity'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data,f,ensure_ascii=False, indent=4)

    @staticmethod
    def get_file_by_id(file_id):
        data = DataManager.load_data()
        for f in data['files']:
            if f['id'] == file_id:
                return f
        return None
        # ******************************************************
# 🤖 BOT CLASS
# ******************************************************
class RobairBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.user_steps = {} # لإدارة حالة المستخدم
        self.setup_handlers()

    def is_admin(self,user_id):
        return user_id == ADMIN_ID

    def format_size(self,bytes_size):
        return f"{bytes_size/(1024*1024):.2f}"

    def now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def keyboard(self,buttons:list):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for button_row in buttons:
            if isinstance(button_row, list):
                markup.add(*button_row)
            else:
                markup.add(button_row)
        return markup

    def main_menu(self,is_admin=False):
        if is_admin:
            return self.keyboard([
                ['📤 رفع ملف', '📋 الأرشيف'],
                ['🗑️ إدارة الملفات', '📊 الإحصائيات'],
                ['🆘 المساعدة', '🔍 البحث']
            ])
        else:
            return self.keyboard([
                ['📚 المحاضرات', '📖 الشرح'],
                ['🆘 المساعدة']
            ])

    def handle_back(self,message):
        if message.chat.id in self.user_steps:
            del self.user_steps[message.chat.id]
        is_admin = self.is_admin(message.from_user.id)
        self.bot.send_message(message.chat.id,BotMessages.CANCELLED,parse_mode='HTML',reply_markup=self.main_menu(is_admin))
            # ******************************************************
    # 🎯 HANDLERS
    # ******************************************************
    def setup_handlers(self):
        # 1. Start/Help Commands
        @self.bot.message_handler(commands=['start','help'])
        def start_help(m):
            if m.chat.id in self.user_steps:
                del self.user_steps[m.chat.id]
            
            is_admin = self.is_admin(m.from_user.id)
            welcome_msg = BotMessages.WELCOME_ADMIN if is_admin else BotMessages.WELCOME_STUDENT
            self.bot.send_message(m.chat.id,welcome_msg,parse_mode='HTML',reply_markup=self.main_menu(is_admin))

        # 2. Upload Handler (Document type)
        @self.bot.message_handler(content_types=['document'])
        def upload_file(m):
            # يتم تفعيل هذه الدالة فقط إذا كان المستخدم في خطوة انتظار الملف
            if m.chat.id not in self.user_steps or self.user_steps[m.chat.id].get('step') != 'awaiting_file':
                return
                
            doc = m.document
            if doc.mime_type != 'application/pdf':
                self.bot.send_message(m.chat.id,"❌ يرجى إرسال ملف PDF فقط")
                return
            
            # حفظ بيانات الملف وتغيير الحالة لانتظار الاسم
            self.user_steps[m.chat.id].update({'document':doc,'step':'awaiting_name'})
            self.bot.send_message(m.chat.id,BotMessages.FILE_RECEIVED,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))
                    # 3. Main Text Handler (Handles all buttons and inputs)
        @self.bot.message_handler(func=lambda m: True)
        def text_handler(m):
            user_id = m.from_user.id
            chat_id = m.chat.id
            text = m.text.strip()
            is_admin = self.is_admin(user_id)

            # A. معالجة "رجوع" في أي حالة
            if text == '↩️ رجوع':
                self.handle_back(m)
                return

            # B. معالجة الحالات (الحفظ والحذف والبحث) - الأولوية للحالة
            if chat_id in self.user_steps:
                step_info = self.user_steps[chat_id]
                
                # B.1. حالة إدخال اسم الملف (UPLOAD: awaiting_name)
                if step_info.get('step') == 'awaiting_name':
                    if len(text) < 2:
                        self.bot.send_message(chat_id,"❌ يرجى إدخال اسم ملف صالح")
                        return
                        
                    self.user_steps[chat_id]['name'] = text
                    self.user_steps[chat_id]['step'] = 'awaiting_section'
                    self.bot.send_message(chat_id, BotMessages.FILE_NAME_SAVED, parse_mode='HTML', 
                                        reply_markup=self.keyboard([['📚 المحاضرات', '📖 الشرح'], ['↩️ رجوع']]))
                    return
                
                # B.2. حالة اختيار القسم (UPLOAD: awaiting_section) - FIX: هذه هي الخطوة التي كانت تتضارب
                if step_info.get('step') == 'awaiting_section':
                    section = text.replace('📚 ','').replace('📖 ','')
                    if section not in ['المحاضرات','الشرح']:
                        self.bot.send_message(chat_id,"❌ يرجى الاختيار من الأزرار")
                        return
                    
                    try:
                        data = DataManager.load_data()
                        doc = self.user_steps[chat_id]['document']
                        new_id = data['next_id']
                        # ضمان اسم ملف فريد
                        path = os.path.join(UPLOAD_FOLDER, f"{new_id}_{doc.file_id}_{doc.file_name}")
                        
                        f_info = self.bot.get_file(doc.file_id)
                        downloaded = self.bot.download_file(f_info.file_path)
                        
                        with open(path,'wb') as f: f.write(downloaded)
                        
                        file_data = {
                            'id': new_id,
                            'name': self.user_steps[chat_id]['name'],
                            'subject': section,
                            'file_path': path,
                            'file_id_telegram': doc.file_id,
                            'file_name': doc.file_name,
                            'size_mb': self.format_size(doc.file_size),
                            'upload_time': self.now(),
                            'timestamp': time.time()
                        }
                        
                        data['files'].append(file_data)
                        data['next_id'] += 1
                        data['stats']['total_uploads'] += 1
                        DataManager.save_data(data)
                        
                        success_msg = BotMessages.FILE_UPLOAD_SUCCESS.format(**file_data)
                        self.bot.send_message(chat_id, success_msg, parse_mode='HTML', reply_markup=self.main_menu(True))
                        del self.user_steps[chat_id]
                        
                    except Exception as e:
                        logging.error(f"خطأ في رفع الملف: {e}")
                        self.bot.send_message(chat_id, f"❌ حدث خطأ أثناء حفظ الملف: {str(e)}")
                        if chat_id in self.user_steps: del self.user_steps[chat_id]
                    return

                # B.3. حالة إدخال معرف الحذف (DELETE: awaiting_delete_id)
                if step_info.get('step') == 'awaiting_delete_id' and text.isdigit():
                    file_id = int(text)
                    file_data = DataManager.get_file_by_id(file_id)
                    
                    if not file_data:
                        self.bot.send_message(chat_id,"❌ لم يتم العثور على الملف")
                        return
                    
                    try:
                        data = DataManager.load_data()
                        # حذف الملف من القائمة
                        data['files'] = [f for f in data['files'] if f['id'] != file_id]
                        DataManager.save_data(data)
                        
                        # حذف الملف من التخزين المحلي
                        if os.path.exists(file_data['file_path']):
                            os.remove(file_data['file_path'])
                        
                        success_msg = BotMessages.DELETE_SUCCESS.format(name=file_data['name'], file_id=file_data['id'])
                        self.bot.send_message(chat_id, success_msg, parse_mode='HTML', reply_markup=self.main_menu(True))
                        del self.user_steps[chat_id]
                        
                    except Exception as e:
                        logging.error(f"خطأ في عملية الحذف: {e}")
                        self.bot.send_message(chat_id, f"❌ حدث خطأ أثناء الحذف: {str(e)}")
                    return
                
                # B.4. حالة إدخال مصطلح البحث (SEARCH: search)
                if step_info.get('step') == 'search':
                    query = text.lower()
                    data = DataManager.load_data()
                    results = [f for f in data['files'] if query in f['name'].lower() or query in f['subject'].lower()]
                    
                    if not results:
                        self.bot.send_message(chat_id,"❌ لا توجد نتائج للبحث", reply_markup=self.keyboard(['↩️ رجوع']))
                        return
                    
                    msg = "🔍 <b>نتائج البحث:</b>\n\n"
                    for f in results:
                        emoji = '📚' if f['subject'] == 'المحاضرات' else '📖'
                        msg += f"{emoji} <b>{f['id']}.</b> {f['name']}\n"
                        msg += f"   └─ 📂 {f['subject']} | 📦 {f['size_mb']} م.ب\n\n"
                    
                    msg += "📥 <i>أرسل رقم الملف للتحميل</i>"
                    self.bot.send_message(chat_id, msg, parse_mode='HTML', reply_markup=self.keyboard(['↩️ رجوع']))
                    self.user_steps[chat_id]['step'] = 'awaiting_download'
                    return
                
                # B.5. حالة التحميل بعد البحث (SEARCH: awaiting_download)
                if step_info.get('step') == 'awaiting_download' and text.isdigit():
                    file_id = int(text)
                    file_data = DataManager.get_file_by_id(file_id)
                    
                    if not file_data:
                        self.bot.send_message(chat_id,"❌ لم يتم العثور على الملف")
                        return
                    
                    self.send_file_to_user(m, file_data)
                    del self.user_steps[chat_id]
                    return

                # B.6. إذا كان في حالة ولكن أدخل نص غير متوقع
                self.bot.send_message(chat_id, "❌ إدخال غير صحيح في هذه الخطوة.", reply_markup=self.keyboard(['↩️ رجوع']))
                return
            
            # C. معالجة أزرار القائمة الرئيسية والأوامر العامة (بدون حالة)
            
            # C.1. معالجة التحميل برقم الملف (بدون حالة)
            if text.isdigit():
                file_id = int(text)
                file_data = DataManager.get_file_by_id(file_id)
                if file_data:
                    self.send_file_to_user(m, file_data)
                    return

            # C.2. معالجة أزرار قائمة المسؤول
            if is_admin:
                if text == '📤 رفع ملف':
                    self.bot.send_message(chat_id,BotMessages.FILE_UPLOAD_START,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))
                    self.user_steps[chat_id]={'step':'awaiting_file','action':'upload'}
                    return
                
                elif text == '📋 الأرشيف':
                    self.show_archive(m, all_files=True)
                    return
                
                elif text == '🗑️ إدارة الملفات':
                    self.delete_start(m)
                    return
                
                elif text == '📊 الإحصائيات':
                    self.show_stats(m)
                    return
                
                elif text == '🔍 البحث':
                    self.bot.send_message(chat_id,"🔍 اكتب كلمة البحث (اسم الملف أو القسم):", reply_markup=self.keyboard(['↩️ رجوع']))
                    self.user_steps[chat_id] = {'step': 'search'}
                    return

            # C.3. معالجة أزرار قائمة الطالب (والمسؤول)
            if text in ['📚 المحاضرات', '📖 الشرح']:
                self.show_section(m)
                return
            
            # C.4. معالجة المساعدة
            if text == '🆘 المساعدة':
                 self.bot.send_message(chat_id, "ℹ️ هذه هي قائمة الأوامر المتاحة لك.", reply_markup=self.main_menu(is_admin))
                 return
            
            # D. آخر حل (نص غير مفهوم)
            self.bot.send_message(chat_id, BotMessages.UNRECOGNIZED, parse_mode='HTML', reply_markup=self.main_menu(is_admin))
                        # ******************************************************
        # 🤝 الدوال المساعدة (للقوائم والوظائف)
        # ******************************************************
        
        def send_file_to_user(m, file_data):
            """دالة موحدة لإرسال الملف وتحديث الإحصائيات"""
            try:
                self.bot.send_document(m.chat.id, file_data['file_id_telegram'], 
                                    caption=f"<b>📄 {file_data['name']}</b>\n📦 الحجم: {file_data['size_mb']} م.ب", 
                                    parse_mode='HTML')
            except Exception as e:
                logging.error(f"خطأ في إرسال الملف باستخدام ID: {e}")
                try:
                    with open(file_data['file_path'],'rb') as file:
                        self.bot.send_document(m.chat.id, file, 
                                            caption=f"<b>📄 {file_data['name']}</b>\n📦 الحجم: {file_data['size_mb']} م.ب", 
                                            parse_mode='HTML')
                except Exception as e:
                    self.bot.send_message(m.chat.id, f"❌ تعذر إرسال الملف: {str(e)}")
                    return

            data = DataManager.load_data()
            data['stats']['total_downloads'] += 1
            DataManager.save_data(data)
            
        def show_section(m):
            """دالة لعرض ملفات المحاضرات أو الشرح"""
            section = 'المحاضرات' if m.text == '📚 المحاضرات' else 'الشرح'
            data = DataManager.load_data()
            section_files = [f for f in data['files'] if f['subject'] == section]
            
            if not section_files:
                self.bot.send_message(m.chat.id, BotMessages.NO_FILES, parse_mode='HTML', reply_markup=self.main_menu(self.is_admin(m.from_user.id)))
                return
            
            emoji = '📚' if section == 'المحاضرات' else '📖'
            files_list = f"{emoji} <b>قسم {section}</b>\n\n"
            
            for f in section_files:
                files_list += f"🔹 <b>{f['id']}.</b> {f['name']}\n"
                files_list += f"   └─ 📦 {f['size_mb']} م.ب\n\n"
            
            files_list += "📥 <i>أرسل رقم الملف لتحميله</i>"
            self.bot.send_message(m.chat.id, files_list, parse_mode='HTML', reply_markup=self.keyboard(['↩️ رجوع']))

        def show_archive(m, all_files=False):
            """دالة لعرض الأرشيف الكامل للمسؤول"""
            if not self.is_admin(m.from_user.id): return
            
            data = DataManager.load_data()
            if not data['files']:
                self.bot.send_message(m.chat.id,BotMessages.NO_FILES,parse_mode='HTML', reply_markup=self.main_menu(True))
                return
            
            files_list = "<b>📋 الأرشيف الكامل</b>\n\n"
            for f in data['files']:
                emoji = '📚' if f['subject'] == 'المحاضرات' else '📖'
                files_list += f"{emoji} <b>ID {f['id']}:</b> {f['name']} ({f['subject']})\n"
                files_list += f"   └─ 📦 {f['size_mb']} م.ب | 🕒 {f['upload_time']}\n\n"
            
            self.bot.send_message(m.chat.id, files_list, parse_mode='HTML', reply_markup=self.main_menu(True))
        
        def delete_start(m):
            """دالة بدء عملية الحذف"""
            if not self.is_admin(m.from_user.id): return
            
            data = DataManager.load_data()
            if not data['files']:
                self.bot.send_message(m.chat.id,BotMessages.NO_FILES,parse_mode='HTML')
                return

            files_list = "<b>🗑️ الملفات المتاحة للحذف</b>\n\n"
            for f in data['files']:
                emoji = '📚' if f['subject'] == 'المحاضرات' else '📖'
                files_list += f"{emoji} <b>{f['id']}.</b> {f['name']}\n"
            
            files_list += "\n" + BotMessages.DELETE_START
            self.bot.send_message(m.chat.id, files_list, parse_mode='HTML', reply_markup=self.keyboard(['↩️ رجوع']))
            self.user_steps[m.chat.id] = {'step': 'awaiting_delete_id', 'action': 'delete'}

        def show_stats(m):
            """دالة عرض الإحصائيات"""
            if not self.is_admin(m.from_user.id): return
            
            if m.chat.id in self.user_steps: del self.user_steps[m.chat.id]

            data = DataManager.load_data()
            stats = data.get('stats', {})
            lectures = sum(1 for f in data['files'] if f['subject'] == 'المحاضرات')
            explanations = sum(1 for f in data['files'] if f['subject'] == 'الشرح')
            
            stats_msg = f"""
<b>📊 إحصائيات النظام</b>

<b>📁 المحتوى:</b>
├ 📚 المحاضرات: <b>{lectures}</b>
├ 📖 الشرح: <b>{explanations}</b>
└ 📦 الإجمالي: <b>{len(data['files'])}</b>

<b>📈 الأنشطة:</b>
├ ⬆️ الرفوعات: <b>{stats.get('total_uploads', 0)}</b>
└ 📥 التحميلات: <b>{stats.get('total_downloads', 0)}</b>

<b>🕒 آخر نشاط:</b> {stats.get('last_activity', 'غير معروف')}
"""
            self.bot.send_message(m.chat.id, stats_msg, parse_mode='HTML', reply_markup=self.main_menu(True))
                def run(self):
        logging.info("🚀 بدء تشغيل البوت...")
        self.bot.polling(none_stop=True)

if __name__ == '__main__':
    bot_instance = RobairBot(API_TOKEN)
    bot_instance.run()
    
