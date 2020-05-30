#!/bin/sh

# Get audio file path
audio_path=${Http_Path:1}
if [ -z "${audio_path}" ]; then
    audio_path="audio"
fi

# Store standard input into audio file
mkdir -p "$(dirname -- "${audio_path}")"
cat > "${audio_path}"

# Add extension if necessary
if [ "${audio_path}" = "${audio_path%.*}" ]; then
    extension=$(ffprobe -loglevel error -show_format -show_entries format=format_name -print_format csv=p=0 "${audio_path}" | echo $(read x; echo "${x%%,*}"))
    extension=${extension%%,*}
    mv "${audio_path}" "${audio_path}.${extension}"
    audio_path="${audio_path}.${extension}"
fi

# Call essentia with file path
echo Calling essentia_streaming_extractor_music "${audio_path}" 1>&2
essentia_streaming_extractor_music "${audio_path}" - profile.yaml
error_code=$?

# Clean up audio file
rm "${audio_path}"

exit ${error_code}
