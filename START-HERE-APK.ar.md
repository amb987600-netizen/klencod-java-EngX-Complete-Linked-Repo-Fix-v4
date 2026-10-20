# EngX — ابدأ هنا للمستودع المرتبط بـ Klencod

افتح أولًا [دليل تحديث المستودع](REPLACE-LINKED-REPO.ar.md). يحتوي خطوات الهاتف وأداة اختيارية للكمبيوتر لمعاينة التحديث ونسخ workflows أندرويد القديمة احتياطيًا قبل تعطيلها.

1. فك ZIP وانسخ **المحتويات كاملة** إلى جذر المستودع، بما فيها `.github`.
2. استبدل `.github/workflows/android-apk.yml`، وأزل workflow أندرويد القديم **Build Android Java APK** من `.github/workflows/` دون حذف workflows غير المرتبطة.
3. اعمل Commit وPush للتعديلات، ثم شغّل **Actions → Build EngX Android APK → Run workflow** على الفرع المحدث. لا تعِد تشغيل المحاولة القديمة.
4. تحقق من العلامة `ENGX_CAPACITOR_REPO_FIX_V2` في السجل. بعد النجاح نزّل **EngX-debug-APK** من Artifacts.

البناء يستخدم Node 22 وJDK 21 وحزم SDK 35 الصالحة، ثم يثبت npm ويبني الويب ويزامن Capacitor من جذر التطبيق، ثم يشغّل Gradle Wrapper داخل `android/`.

هذه حزمة مصدر وليست APK جاهزًا. [نتائج التحقق الفعلية وحدوده](docs/REPLACEMENT-VERIFICATION.ar.md): لم نشغّل GitHub/Klencod في حسابك، ولم نختبر التطبيق على هاتف. لا تعني اختبارات الويب نجاح تجميع Android.
