local mcproto = Proto("mcproto", "Bambu MC wire protocol")
local mccommands = DissectorTable.new("mcproto.command", "Bambu MC protocol commands", ftypes.UINT16, base.HEX, mcproto)

local devices = {
	[3] = "MC",
	[6] = "AP",
	[7] = "AMS",
	[8] = "TH",
	[9] = "AP2",
	[0xE] = "AHB",
	[0xF] = "EXT",
	[0x13] = "CTC",
}

local fields = {
	capture_source = ProtoField.uint8("mcproto.capture_source", "Capture source", nil,
		{ [1] = "Serial port write from forward", [2] = "Serial port read from forward" }),
	flags = ProtoField.uint8("mcproto.flags", "Flags", base.HEX),
	flags_wants_response = ProtoField.bool("mcproto.flags.wants_response", "RPC wants response", ftypes.UINT8, nil, 0x01),
	flags_is_initiator = ProtoField.bool("mcproto.flags.is_initiator", "Message is initiator", ftypes.UINT8, nil, 0x04),
	request = ProtoField.framenum('mcproto.request', 'Request', base.NONE, frametype.REQUEST),
	response = ProtoField.framenum('mcproto.response', 'Response', base.NONE, frametype.RESPONSE),
	seq = ProtoField.uint16("mcproto.seq", "Sequence number", base.DEC),
	dest = ProtoField.uint16("mcproto.dest", "Destination", nil, devices),
	src = ProtoField.uint16("mcproto.src", "Source", nil, devices),
	command = ProtoField.uint8("mcproto.command", "Command", base.HEX),
	payload = ProtoField.none("mcproto.payload", "Payload"),
}

mcproto.fields = { }

local reqmap = {}
local respmap = {}

for _,v in pairs(fields) do table.insert(mcproto.fields,v) end

local f_src = Field.new("mcproto.src")
local f_dest = Field.new("mcproto.dest")
local f_seq = Field.new("mcproto.seq")
local f_wants_response = Field.new("mcproto.flags.wants_response")
local f_is_initiator = Field.new("mcproto.flags.is_initiator")
local f_command = Field.new("mcproto.command")

function mcproto.dissector(buf, pinfo, root)
	pinfo.cols.protocol:set("MCPROTO")
	local length = buf:len()
	if length == 0 then return 0 end
	
	local tree = root:add(mcproto, buf:range(1,len), "Bambu bus protocol data")
	tree:add(fields.capture_source, buf:range(0, 1))
	local flag_tree = tree:add(fields.flags, buf:range(2, 1))
		flag_tree:add(fields.flags_wants_response, buf:range(2, 1))
		flag_tree:add(fields.flags_is_initiator, buf:range(2, 1))

	tree:add_le(fields.seq, buf:range(3, 2))
	local seq = f_seq()()
	local is_initiator = f_is_initiator()()
	
	if not pinfo.visited then
		if is_initiator then
			reqmap[seq] = reqmap[seq] or {}
			table.insert(reqmap[seq], pinfo.number)
		else
			respmap[seq] = respmap[seq] or {}
			table.insert(respmap[seq], pinfo.number)
		end
	end
	
	if is_initiator and respmap[seq] then
		for _,pnum2 in ipairs(respmap[seq]) do
			if pnum2 > pinfo.number then
				tree:add(fields.response, pnum2)
				break
			end
		end
	end
	if (not is_initiator) and reqmap[seq] then
		local last_pnum2 = nil
		for _,pnum2 in ipairs(reqmap[seq]) do
			if pnum2 < pinfo.number then
				last_pnum2 = pnum2
			end
		end
		if last_pnum2 then tree:add(fields.request, last_pnum2) end
	end
	-- look at packet length, and add an expert to complain if needed
	-- look at CRC, and add an expert to complain if needed
	
	pinfo.cols.info:set("[" .. (is_initiator and (f_wants_response()() and "REQ " or "") or "RSP ") .. "#" .. seq .. "] ")
	
	tree:add(fields.dest, buf:range(8, 2))
	tree:add(fields.src, buf:range(10, 2))
	
	pinfo.cols.src:set(devices[f_src()()] or f_src()())
	pinfo.cols.dst:set(devices[f_dest()()] or f_dest()())

	tree:add_le(fields.command, buf:range(12, 2)) -- really, { command_set, command_id }, but this is much easier
	
	local payload = buf:range(14, length - 16)
	mccommands:try(f_command()(), payload:tvb(), pinfo, tree)
end

-- Now for some commands!
function mk_cmd(cmdset, cmdid, name, fields, dis)
	local myname = "mcproto." .. name
	local proto = Proto(myname, name)
	proto.fields = {}
	for _,v in pairs(fields) do table.insert(proto.fields,v) end
	proto.dissector = function (buf, pinfo, root) return dis(proto, fields, buf, pinfo, root) end
	mccommands:set(cmdset * 256 + cmdid, proto)
	return proto
end

function mk_cmd_opaque(cmdset, cmdid, name)
	local myname = "mcproto." .. name
	mk_cmd(cmdset, cmdid, name,
		{ payload = ProtoField.bytes(myname..".payload", "Payload") },
		function (proto, fields, buf, pinfo, root)
			local len = buf:len()
			local tree = root:add(proto, buf:range(0, len), name)
			tree:add(fields.payload, buf:range(0, len))
			pinfo.cols.info:append(name)
		end)
end

mk_cmd_opaque(1, 1, "ping")
mk_cmd_opaque(1, 3, "get_version")
mk_cmd_opaque(1, 4, "sync_timestamp")
mk_cmd_opaque(1, 6, "mcu_upgrade")
mk_cmd_opaque(1, 8, "mcu_hms")
mk_cmd_opaque(1, 9, "factory_reset")
mk_cmd_opaque(2, 5, "gcode_execute_state")
mk_cmd_opaque(2, 6, "gcode_request")
mk_cmd(2, 9, "mcu_display_message",
	{ message = ProtoField.string("mcproto.mcu_display_message.message", "Message") },
	function (proto, fields, buf, pinfo, root)
		local len = buf:len()
		local tree = root:add(proto, buf:range(0, len), "mcu_display_message")
		tree:add(fields.message, buf:range(0, len))
		pinfo.cols.info:append("mcu_display_message: \""..buf:range(0, len):string().."\"")
	end
)
	
mk_cmd_opaque(2, 10, "vosync")
mk_cmd_opaque(2, 11, "gcode_ctx")
mk_cmd_opaque(2, 12, "mc_state")
mk_cmd_opaque(2, 15, "link_ams_report")
mk_cmd_opaque(2, 17, "ack_tray_info")
mk_cmd_opaque(2, 22, "gcode_line_handle")
mk_cmd_opaque(2, 23, "ams_mapping")
mk_cmd_opaque(2, 24, "ams_tray_info_write_ack")
mk_cmd_opaque(2, 25, "ams_user_settings")
mk_cmd_opaque(2, 27, "hw_info_voltage")
mk_cmd_opaque(2, 28, "link_ams_tray_consumption_ack")
mk_cmd_opaque(2, 29, "pack_get_part_info_ack")
mk_cmd_opaque(2, 34, "extrusion_result_update")
mk_cmd_opaque(2, 36, "fila_ams_get")
mk_cmd_opaque(2, 37, "mc_get_skipped_obj_list")

mk_cmd_opaque(3, 1, "M971")
mk_cmd_opaque(3, 2, "M972")
mk_cmd_opaque(3, 5, "M963")
mk_cmd_opaque(3, 7, "M969")
mk_cmd_opaque(3, 6, "M965_b")
mk_cmd_opaque(3, 9, "M967")
mk_cmd_opaque(3, 11, "M973")
mk_cmd_opaque(3, 14, "M965")
mk_cmd_opaque(3, 49, "MC_M976")

mk_cmd_opaque(3, 50, "M977")
mk_cmd_opaque(3, 51, "M978")
mk_cmd_opaque(3, 52, "M981")
mk_cmd_opaque(3, 53, "M991")
mk_cmd_opaque(3, 81, "M987")
mk_cmd_opaque(3, 82, "SENSORCHECK")

mk_cmd_opaque(4, 1, "set_module_sn")
mk_cmd_opaque(4, 2, "get_module_sn")
mk_cmd_opaque(4, 3, "inject_module_key")
mk_cmd_opaque(4, 4, "get_inject_status")
mk_cmd_opaque(4, 5, "mcu_reboot")
mk_cmd_opaque(4, 6, "send_to_amt_core")
mk_cmd_opaque(4, 7, "set_module_lifecycle")
mk_cmd_opaque(4, 8, "get_module_lifecycle")
mk_cmd_opaque(4, 10, "inject_productcode")
mk_cmd_opaque(4, 11, "get_productcode")
