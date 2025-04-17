#!/bin/sh


# Get audio file path if given
audio_path="$AUDIO_PATH"
if [ -z "${audio_path}" ]; then
    audio_path="audio"
fi

# Link audio data to audio path
mkdir -p "$(dirname -- "${audio_path}")"
ln $AUDIO_DATA "${audio_path}"

# Call Sonic Annotator with arguments and file path
arguments=$(echo "$@" | jq -r ". | to_entries[] | [.key, .value] | .[]")
echo Calling sonic-annotator ${arguments} "${audio_path}" > /dev/null
sonic-annotator ${arguments} "${audio_path}" 2> /dev/null
error_code=$?

# Clean up audio file
rm "${audio_path}"

exit ${error_code}
