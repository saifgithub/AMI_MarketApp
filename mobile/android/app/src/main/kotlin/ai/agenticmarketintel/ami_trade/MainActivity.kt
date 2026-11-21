package ai.agenticmarketintel.ami_trade

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.provider.OpenableColumns
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Hosts the Flutter UI and one native bridge, `export_save` (DEF524): opens the
 * system Save dialog (Storage Access Framework ACTION_CREATE_DOCUMENT) and
 * writes the account-data export there, so the file can stay on a phone that
 * has no Files app and only share targets that send it elsewhere.
 */
class MainActivity : FlutterActivity() {
    private var pendingResult: MethodChannel.Result? = null
    private var pendingBytes: ByteArray? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                if (call.method != "saveFile") {
                    result.notImplemented()
                    return@setMethodCallHandler
                }
                val name = call.argument<String>("name")
                val mime = call.argument<String>("mime")
                val bytes = call.argument<ByteArray>("bytes")
                if (name == null || mime == null || bytes == null) {
                    result.error("bad_args", "name, mime and bytes are required", null)
                    return@setMethodCallHandler
                }
                if (pendingResult != null) {
                    result.error("busy", "A save is already in progress", null)
                    return@setMethodCallHandler
                }
                pendingResult = result
                pendingBytes = bytes
                val intent = Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = mime
                    putExtra(Intent.EXTRA_TITLE, name)
                }
                try {
                    startActivityForResult(intent, REQUEST_SAVE)
                } catch (e: Exception) {
                    finishSave { it.error("no_dialog", e.message, null) }
                }
            }
    }

    @Deprecated("FlutterActivity still routes results through this callback")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        if (requestCode != REQUEST_SAVE) {
            super.onActivityResult(requestCode, resultCode, data)
            return
        }
        val uri: Uri? = data?.data
        if (resultCode != Activity.RESULT_OK || uri == null) {
            finishSave { it.success(null) }
            return
        }
        val bytes = pendingBytes
        try {
            val out = contentResolver.openOutputStream(uri, "wt")
                ?: throw java.io.IOException("No output stream for $uri")
            out.use { it.write(bytes ?: ByteArray(0)) }
            val shown = displayName(uri)
            finishSave { it.success(shown) }
        } catch (e: Exception) {
            finishSave { it.error("write_failed", e.message, null) }
        }
    }

    private fun displayName(uri: Uri): String {
        contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)
            ?.use { c ->
                if (c.moveToFirst()) {
                    val n = c.getString(0)
                    if (!n.isNullOrEmpty()) return n
                }
            }
        return uri.lastPathSegment ?: "ami-data-export.json"
    }

    private fun finishSave(reply: (MethodChannel.Result) -> Unit) {
        val r = pendingResult
        pendingResult = null
        pendingBytes = null
        if (r != null) reply(r)
    }

    companion object {
        private const val CHANNEL = "ai.agenticmarketintel.ami_trade/export_save"
        private const val REQUEST_SAVE = 5240
    }
}
