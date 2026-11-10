plugins {
    id("com.android.application")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

// Supplied by Codemagic's signing identities or the local process environment. Never write
// passwords to key.properties or fall back to the development certificate for a release.
val releaseSigningEnvironment = listOf(
    "CM_KEYSTORE_PATH", "CM_KEYSTORE_PASSWORD", "CM_KEY_ALIAS", "CM_KEY_PASSWORD",
).associateWith { providers.environmentVariable(it).orNull }

val validateReleaseSigning by tasks.registering {
    group = "verification"
    description = "Require externally supplied signing material for every release build."
    doLast {
        val missing = releaseSigningEnvironment.filterValues { it.isNullOrBlank() }.keys
        if (missing.isNotEmpty()) {
            throw GradleException("Release signing is required. Set: ${missing.joinToString()}. " +
                "Use external signing material; debug signing is not a release fallback.")
        }
        if (!file(releaseSigningEnvironment.getValue("CM_KEYSTORE_PATH")!!).isFile) {
            throw GradleException("Release signing keystore is unavailable at CM_KEYSTORE_PATH.")
        }
    }
}

tasks.matching { it.name == "preReleaseBuild" }.configureEach {
    dependsOn(validateReleaseSigning)
}

android {
    namespace = "dev.changelens.app"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "dev.changelens.app"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        // Uses the version code from pubspec.yaml. When using split APKs, 1000 * ABI_VERSION
        // is added automatically by Flutter. (https://developer.android.com/studio/build/configure-apk-splits#configure-APK-versions)
        // You can force using the value of versionCode by specifying the `-P force-version-code-ignoring-abi=true`
        // flag during build.
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            storeFile = releaseSigningEnvironment["CM_KEYSTORE_PATH"]?.let { file(it) }
            storePassword = releaseSigningEnvironment["CM_KEYSTORE_PASSWORD"]
            keyAlias = releaseSigningEnvironment["CM_KEY_ALIAS"]
            keyPassword = releaseSigningEnvironment["CM_KEY_PASSWORD"]
        }
    }

    buildTypes {
        release {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

kotlin {
    compilerOptions {
        jvmTarget = org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17
    }
}

flutter {
    source = "../.."
}
