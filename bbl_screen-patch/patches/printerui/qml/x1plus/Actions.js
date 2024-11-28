.pragma library
.import "Binding.js" as Binding

/* QML interface to send X1Plus Actions (and handle X1Plus Actions aimed at
 * the UI, eventually)
 *
 * Copyright (c) 2024 Joshua Wise, and the X1Plus authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

var X1Plus = null;

var _executeThunk = null;

function execute(action) {
	_executeThunk(action);
}

function awaken() {
	_executeThunk = X1Plus.DBus.proxyFunction("x1plus.x1plusd", "/x1plus/actions", "x1plus.actions", "Execute");
}
