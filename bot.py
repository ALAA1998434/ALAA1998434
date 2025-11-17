import telebot
import os
import json
import time
from datetime import datetime
import logging
import re

# ******************************************************
# 🔧 CONFIGURATION SETTINGS
# ******************************************************
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
    FILE_UPLOAD_SUCCESS = "<b>🎉 تم رفع الملف بنجاح!</b>\n📄 <b>الاسم:</b> {name}\n📂 <b>القسم:</b> {subject}\n🆔 <b>المعرف:</b> {file_id}\n📦 <b>الحجم:</b> {size}\n🕒 <b>الوقت:</b> {time}"
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
# 🤖 ROBOT BOT CLASS
# ******************************************************
class RobairBot:
    def __init__(self, token):
        self.bot = telebot.TeleBot(token)
        self.user_steps = {}  # لحفظ حالة المستخدم
        self.setup_handlers()

    # --- Helpers ---
    def is_admin(self,user_id):
        return user_id == ADMIN_ID

    def now(self):
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def format_size(self,bytes_size):
        return f"{bytes_size/(1024*1024):.2f} م.ب"

    def keyboard(self,buttons:list):
        markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
        for row in buttons:
            if isinstance(row,list):
                markup.add(*row)
            else:
                markup.add(row)
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
        self.bot.send_message(message.chat.id,BotMessages.CANCELLED,parse_mode='HTML',
                              reply_markup=self.main_menu(self.is_admin(message.from_user.id)))

    # --- Core Handlers ---
    def setup_handlers(self):
        @self.bot.message_handler(commands=['start','help'])
        def start_help(m):
            if m.chat.id in self.user_steps:
                del self.user_steps[m.chat.id]
            is_admin = self.is_admin(m.from_user.id)
            welcome_msg = BotMessages.WELCOME_ADMIN if is_admin else BotMessages.WELCOME_STUDENT
            self.bot.send_message(m.chat.id,welcome_msg,parse_mode='HTML',reply_markup=self.main_menu(is_admin))

        @self.bot.message_handler(content_types=['document'])
        def upload_file(m):
            if m.chat.id not in self.user_steps or self.user_steps[m.chat.id].get('step') != 'awaiting_file':
                return
            doc = m.document
            if doc.mime_type != 'application/pdf':
                self.bot.send_message(m.chat.id,"❌ يرجى إرسال ملف PDF فقط")
                return
            self.user_steps[m.chat.id].update({'document':doc,'step':'awaiting_name'})
            self.bot.send_message(m.chat.id,BotMessages.FILE_RECEIVED,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))

        @self.bot.message_handler(func=lambda m: True)
        def text_handler(m):
            chat_id = m.chat.id
            user_id = m.from_user.id
            text = m.text.strip()
            is_admin = self.is_admin(user_id)

            # رجوع
            if text == '↩️ رجوع':
                self.handle_back(m)
                return

            # معالجة الخطوات
            if chat_id in self.user_steps:
                step = self.user_steps[chat_id].get('step')

                # إدخال اسم الملف
                if step == 'awaiting_name':
                    if len(text)<2:
                        self.bot.send_message(chat_id,"❌ يرجى إدخال اسم ملف صالح")
                        return
                    self.user_steps[chat_id]['name'] = text
                    self.user_steps[chat_id]['step'] = 'awaiting_section'
                    self.bot.send_message(chat_id, BotMessages.FILE_NAME_SAVED, parse_mode='HTML', 
                                          reply_markup=self.keyboard([['📚 المحاضرات', '📖 الشرح'], ['↩️ رجوع']]))
                    return

                # اختيار القسم
                if step == 'awaiting_section':
                    if text not in ['📚 المحاضرات','📖 الشرح']:
                        self.bot.send_message(chat_id,"❌ يرجى الاختيار من الأزرار")
                        return
                    section = 'المحاضرات' if text == '📚 المحاضرات' else 'الشرح'
                    try:
                        data = DataManager.load_data()
                        doc = self.user_steps[chat_id]['document']
                        new_id = data['next_id']
                        safe_name = re.sub(r'[^\w\-_\. ]','_',doc.file_name)
                        path = os.path.join(UPLOAD_FOLDER,f"{new_id}_{doc.file_id}_{safe_name}")
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
                            'size': self.format_size(doc.file_size),
                            'upload_time': self.now(),
                            'timestamp': time.time()
                        }

                        data['files'].append(file_data)
                        data['next_id'] += 1
                        data['stats']['total_uploads'] += 1
                        DataManager.save_data(data)

                        msg = BotMessages.FILE_UPLOAD_SUCCESS.format(**file_data)
                        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.main_menu(True))
                        del self.user_steps[chat_id]

                    except Exception as e:
                        logging.error(f"خطأ في رفع الملف: {e}")
                        self.bot.send_message(chat_id,f"❌ حدث خطأ أثناء حفظ الملف: {str(e)}")
                        if chat_id in self.user_steps: del self.user_steps[chat_id]
                    return

                # حالة إدخال معرف الحذف
                if step == 'awaiting_delete_id' and text.isdigit():
                    self.delete_file_by_id(chat_id,int(text))
                    return

                # البحث
                if step == 'search':
                    self.search_files(chat_id,text)
                    return

                # التحميل بعد البحث
                if step == 'awaiting_download' and text.isdigit():
                    file_id = int(text)
                    file_data = DataManager.get_file_by_id(file_id)
                    if file_data: self.send_file_to_user(chat_id,file_data)
                    del self.user_steps[chat_id]
                    return

                # نص غير متوقع
                self.bot.send_message(chat_id,"❌ إدخال غير صحيح في هذه الخطوة.",reply_markup=self.keyboard(['↩️ رجوع']))
                return

            # --- Buttons بدون حالة ---
            if is_admin:
                if text == '📤 رفع ملف':
                    self.bot.send_message(chat_id,BotMessages.FILE_UPLOAD_START,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))
                    self.user_steps[chat_id]={'step':'awaiting_file'}
                    return
                elif text == '📋 الأرشيف':
                    self.show_archive(chat_id)
                    return
                elif text == '🗑️ إدارة الملفات':
                    self.delete_start(chat_id)
                    return
                elif text == '📊 الإحصائيات':
                    self.show_stats(chat_id)
                    return
                elif text == '🔍 البحث':
                    self.bot.send_message(chat_id,"🔍 اكتب كلمة البحث (اسم الملف أو القسم):", reply_markup=self.keyboard(['↩️ رجوع']))
                    self.user_steps[chat_id] = {'step':'search'}
                    return

            if text in ['📚 المحاضرات','📖 الشرح']:
                self.show_section(chat_id,'المحاضرات' if text=='📚 المحاضرات' else 'الشرح')
                return

            if text == '🆘 المساعدة':
                self.bot.send_message(chat_id,"ℹ️ هذه هي قائمة الأوامر المتاحة لك.", reply_markup=self.main_menu(is_admin))
                return

            # نص غير معروف
            self.bot.send_message(chat_id,BotMessages.UNRECOGNIZED,parse_mode='HTML',reply_markup=self.main_menu(is_admin))

    # --- Utility Methods ---
    def send_file_to_user(self,chat_id,file_data):
        try:
            self.bot.send_document(chat_id,file_data['file_id_telegram'],caption=f"<b>📄 {file_data['name']}</b>\n📦 {file_data['size']}",parse_mode='HTML')
        except:
            try:
                with open(file_data['file_path'],'rb') as f:
                    self.bot.send_document(chat_id,f,caption=f"<b>📄 {file_data['name']}</b>\n📦 {file_data['size']}",parse_mode='HTML')
            except Exception as e:
                self.bot.send_message(chat_id,f"❌ تعذر إرسال الملف: {str(e)}")
                return
        data = DataManager.load_data()
        data['stats']['total_downloads'] += 1
        DataManager.save_data(data)

    def show_section(self,chat_id,section):
        data = DataManager.load_data()
        files = [f for f in data['files'] if f['subject']==section]
        if not files:
            self.bot.send_message(chat_id,BotMessages.NO_FILES,parse_mode='HTML',reply_markup=self.main_menu(self.is_admin(chat_id)))
            return
        emoji = '📚' if section=='المحاضرات' else '📖'
        msg = f"{emoji} <b>قسم {section}</b>\n\n"
        for f in files:
            msg += f"🔹 <b>{f['id']}.</b> {f['name']}\n   └─ 📦 {f['size']}\n\n"
        msg += "📥 <i>أرسل رقم الملف لتحميله</i>"
        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))

    def show_archive(self,chat_id):
        if not self.is_admin(chat_id): return
        data = DataManager.load_data()
        if not data['files']:
            self.bot.send_message(chat_id,BotMessages.NO_FILES,parse_mode='HTML',reply_markup=self.main_menu(True))
            return
        msg = "<b>📋 الأرشيف الكامل</b>\n\n"
        for f in data['files']:
            emoji = '📚' if f['subject']=='المحاضرات' else '📖'
            msg += f"{emoji} <b>ID {f['id']}:</b> {f['name']} ({f['subject']})\n   └─ 📦 {f['size']} | 🕒 {f['upload_time']}\n\n"
        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.main_menu(True))

    def delete_start(self,chat_id):
        if not self.is_admin(chat_id): return
        data = DataManager.load_data()
        if not data['files']:
            self.bot.send_message(chat_id,BotMessages.NO_FILES,parse_mode='HTML')
            return
        msg = "<b>🗑️ الملفات المتاحة للحذف</b>\n\n"
        for f in data['files']:
            emoji = '📚' if f['subject']=='المحاضرات' else '📖'
            msg += f"{emoji} <b>{f['id']}.</b> {f['name']}\n"
        msg += "\n" + BotMessages.DELETE_START
        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))
        self.user_steps[chat_id] = {'step':'awaiting_delete_id'}

    def delete_file_by_id(self,chat_id,file_id):
        file_data = DataManager.get_file_by_id(file_id)
        if not file_data:
            self.bot.send_message(chat_id,"❌ لم يتم العثور على الملف")
            return
        try:
            data = DataManager.load_data()
            data['files'] = [f for f in data['files'] if f['id']!=file_id]
            DataManager.save_data(data)
            if os.path.exists(file_data['file_path']):
                os.remove(file_data['file_path'])
            msg = BotMessages.DELETE_SUCCESS.format(name=file_data['name'],file_id=file_data['id'])
            self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.main_menu(True))
        except Exception as e:
            logging.error(f"خطأ في الحذف: {e}")
            self.bot.send_message(chat_id,f"❌ حدث خطأ أثناء الحذف: {str(e)}")

    def search_files(self,chat_id,query):
        query = query.lower()
        data = DataManager.load_data()
        results = [f for f in data['files'] if query in f['name'].lower() or query in f['subject'].lower()]
        if not results:
            self.bot.send_message(chat_id,"❌ لا توجد نتائج للبحث",reply_markup=self.keyboard(['↩️ رجوع']))
            return
        msg = "🔍 <b>نتائج البحث:</b>\n\n"
        for f in results:
            emoji = '📚' if f['subject']=='المحاضرات' else '📖'
            msg += f"{emoji} <b>{f['id']}.</b> {f['name']}\n   └─ 📂 {f['subject']} | 📦 {f['size']}\n\n"
        msg += "📥 <i>أرسل رقم الملف للتحميل</i>"
        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.keyboard(['↩️ رجوع']))
        self.user_steps[chat_id]['step'] = 'awaiting_download'

    def show_stats(self,chat_id):
        if not self.is_admin(chat_id): return
        data = DataManager.load_data()
        stats = data['stats']
        msg = f"<b>📊 الإحصائيات:</b>\n\n"
        msg += f"🗂️ مجموع الملفات المرفوعة: {stats.get('total_uploads',0)}\n"
        msg += f"📥 مجموع التحميلات: {stats.get('total_downloads',0)}\n"
        msg += f"🕒 آخر نشاط: {stats.get('last_activity','-')}\n"
        self.bot.send_message(chat_id,msg,parse_mode='HTML',reply_markup=self.main_menu(True))
``
