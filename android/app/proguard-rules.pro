# Keep stack traces readable if a release build ever crashes.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# kotlinx.serialization: keep generated serializers for @Serializable classes (PC API payloads).
-keepclassmembers @kotlinx.serialization.Serializable class ** {
    *** Companion;
    *** serializer(...);
}
-keep,includedescriptorclasses class app.audiobooks.player.**$$serializer { *; }
-keepclassmembers class app.audiobooks.player.** { *** Companion; }
